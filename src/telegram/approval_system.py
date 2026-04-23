"""
Approval System
Telegram-based approval workflow for model updates and parameter changes.
"""

import uuid
from typing import Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from src.database.repositories import ApprovalHistoryRepository
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ProposalType(Enum):
    """Types of proposals that require approval."""
    MODEL_DEPLOYMENT = "model_deployment"
    PARAMETER_CHANGE = "parameter_change"
    PATTERN_CHANGE = "pattern_change"


@dataclass
class Proposal:
    """Base proposal class."""
    proposal_type: str
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@dataclass
class ModelDeploymentProposal(Proposal):
    """Model deployment proposal."""
    symbol: str = ""
    version_id: int = 0
    current_precision: float = 0.0
    new_precision: float = 0.0
    improvement_pct: float = 0.0
    validation_metrics: Dict = None
    
    def __post_init__(self):
        super().__post_init__()
        if self.validation_metrics is None:
            self.validation_metrics = {}
        if not self.proposal_type:
            self.proposal_type = "model_deployment"


@dataclass
class ParameterChangeProposal(Proposal):
    """Parameter change proposal."""
    params: Dict = None
    test_mode: str = "paper"
    duration_hours: int = 24
    
    def __post_init__(self):
        super().__post_init__()
        if self.params is None:
            self.params = {}
        if not self.proposal_type:
            self.proposal_type = "parameter_change"


class ProposalManager:
    """Manages pending proposals."""
    
    def __init__(self):
        self.approval_repo = ApprovalHistoryRepository()
    
    async def save_proposal(self, proposal_id: str, proposal: Proposal) -> int:
        """Save proposal to database."""
        proposal_dict = asdict(proposal)
        proposal_dict["timestamp"] = proposal_dict["timestamp"].isoformat()
        
        approval_id = await self.approval_repo.save_proposal(
            proposal_id=proposal_id,
            proposal=proposal_dict
        )
        
        logger.info(f"Proposal saved: {proposal_id} (Type: {proposal.proposal_type})")
        return approval_id
    
    async def log_decision(
        self,
        proposal_id: str,
        decision: str,
        admin_id: str,
        timestamp: datetime
    ):
        """Log approval decision."""
        await self.approval_repo.log_decision(
            proposal_id=proposal_id,
            decision=decision,
            admin_id=admin_id,
            timestamp=timestamp
        )
        logger.info(f"Decision logged for {proposal_id}: {decision} by {admin_id}")


class ApprovalHandler:
    """Handles Telegram approval callbacks."""
    
    def __init__(self):
        pass
    
    def handle_approval(self, proposal_id: str, decision: str):
        """Handle approval decision."""
        logger.info(f"Approval handled: {proposal_id} -> {decision}")


class ApprovalSystem:
    """
    Main approval orchestrator.
    Manages proposal submission, Telegram notifications, and decision handling.
    """
    
    def __init__(self, telegram_notifier=None):
        self.notifier = telegram_notifier
        self.proposal_manager = ProposalManager()
        self.approval_handler = ApprovalHandler()
        self._pending_proposals: Dict[str, Proposal] = {}
    
    async def submit_proposal(self, proposal: Proposal):
        """Submit proposal for admin approval."""
        proposal_id = str(uuid.uuid4())
        self._pending_proposals[proposal_id] = proposal
        
        # Save to database
        await self.proposal_manager.save_proposal(proposal_id, proposal)
        
        # Format and send Telegram message
        message = self._format_proposal_message(proposal)
        keyboard = self._create_approval_keyboard(proposal_id)
        
        if self.notifier:
            try:
                await self.notifier.send_message(
                    message,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                logger.info(f"Proposal sent to Telegram: {proposal_id}")
            except Exception as e:
                logger.error(f"Failed to send Telegram notification: {e}")
        else:
            logger.warning(f"No Telegram notifier configured - proposal {proposal_id} not sent")
            # Log proposal for manual review
            logger.info(f"PROPOSAL FOR APPROVAL:\n{message}")
    
    def _format_proposal_message(self, proposal: Proposal) -> str:
        """Format proposal for Telegram."""
        if isinstance(proposal, ModelDeploymentProposal):
            return (
                f"🤖 *Model Deployment Proposal*\n\n"
                f"Symbol: `{proposal.symbol}`\n"
                f"Current Precision: `{proposal.current_precision:.1%}`\n"
                f"New Precision: `{proposal.new_precision:.1%}`\n"
                f"Improvement: `+{proposal.improvement_pct:.1f}%`\n\n"
                f"Validation Metrics:\n"
                f"• OOS Precision: `{proposal.validation_metrics.get('oos_precision', 0):.1%}`\n"
                f"• Sharpe Ratio: `{proposal.validation_metrics.get('sharpe_ratio', 0):.2f}`\n"
                f"• Max Drawdown: `{proposal.validation_metrics.get('max_drawdown_pct', 0):.1f}%`\n"
                f"• Folds: `{proposal.validation_metrics.get('n_folds', 0)}`\n\n"
                f"Approve deployment?"
            )
        elif isinstance(proposal, ParameterChangeProposal):
            params_str = "\n".join(
                f"• {k}: `{v}`" for k, v in proposal.params.items()
            )
            return (
                f"⚙️ *Parameter Change Proposal*\n\n"
                f"New Parameters:\n{params_str}\n\n"
                f"Test Mode: `{proposal.test_mode}`\n"
                f"Duration: `{proposal.duration_hours}h`\n\n"
                f"Approve changes?"
            )
        else:
            return f"📋 *Proposal*\n\nType: {proposal.proposal_type}\n\nApprove?"
    
    def _create_approval_keyboard(self, proposal_id: str):
        """Create Telegram inline keyboard."""
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_{proposal_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_{proposal_id}"),
                ],
                [
                    InlineKeyboardButton("📝 Test in Paper Mode", callback_data=f"paper_{proposal_id}"),
                ],
            ]
            return InlineKeyboardMarkup(keyboard)
        except ImportError:
            logger.warning("python-telegram-bot not installed - cannot create keyboard")
            return None
    
    async def handle_approval(self, proposal_id: str, decision: str, admin_id: str):
        """Handle admin approval decision."""
        proposal = self._pending_proposals.get(proposal_id)
        if not proposal:
            logger.warning(f"Proposal {proposal_id} not found")
            return
        
        # Log decision
        await self.proposal_manager.log_decision(
            proposal_id=proposal_id,
            decision=decision,
            admin_id=admin_id,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Execute based on decision
        if decision == "approve":
            await self._execute_proposal(proposal)
            if self.notifier:
                await self.notifier.send_message(
                    f"✅ Proposal approved and deployed by admin {admin_id}"
                )
        elif decision == "reject":
            if self.notifier:
                await self.notifier.send_message(
                    f"❌ Proposal rejected by admin {admin_id}"
                )
        elif decision == "paper":
            await self._test_in_paper_mode(proposal)
            if self.notifier:
                await self.notifier.send_message(
                    f"📝 Proposal sent to paper trading for testing"
                )
        
        # Remove from pending
        del self._pending_proposals[proposal_id]
    
    async def _execute_proposal(self, proposal: Proposal):
        """Execute approved proposal."""
        if isinstance(proposal, ModelDeploymentProposal):
            await self._deploy_model(proposal)
        elif isinstance(proposal, ParameterChangeProposal):
            await self._apply_parameters(proposal)
    
    async def _deploy_model(self, proposal: ModelDeploymentProposal):
        """Deploy new model to production."""
        from src.ml.self_improvement_engine import DeploymentManager
        
        deployment_manager = DeploymentManager()
        await deployment_manager.deploy_version(proposal.version_id)
        
        logger.info(f"Model deployed for {proposal.symbol} (version {proposal.version_id})")
    
    async def _apply_parameters(self, proposal: ParameterChangeProposal):
        """Apply parameter changes."""
        # This would update configuration
        logger.info(f"Parameters applied: {proposal.params}")
        # TODO: Integrate with configuration system
    
    async def _test_in_paper_mode(self, proposal: Proposal):
        """Test proposal in paper trading mode."""
        logger.info(f"Testing proposal in paper mode: {proposal.proposal_type}")
        # TODO: Integrate with paper trading system
