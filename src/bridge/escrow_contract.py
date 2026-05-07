"""
Escrow Contract Interface
==========================
Web3 bridge to the BSC escrow smart contract.

Contract behaviour:
  - Holds USDT/BUSD on BSC.
  - withdraw() deducts 15% service fee automatically:
      85% → user wallet
      15% → hardcoded SERVICE_WALLET
  - Re-entrancy protected (checks-effects-interactions pattern).
  - Only the contract owner can pause/unpause.

When Web3 / contract is unavailable, all methods return safe mock responses
so the rest of the system keeps working (paper/demo mode).
"""
from __future__ import annotations

import os
from decimal import Decimal
from typing import Optional, Tuple

from src.utils.logger import get_logger

logger = get_logger(__name__)

# ── Contract ABI (minimal — only the functions we call) ──────────────────────
ESCROW_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "user", "type": "address"},
                   {"internalType": "uint256", "name": "amount", "type": "uint256"}],
        "name": "deposit",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "amount", "type": "uint256"}],
        "name": "withdraw",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "paused",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True,  "name": "user",   "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
        ],
        "name": "Deposited",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True,  "name": "user",      "type": "address"},
            {"indexed": False, "name": "net",        "type": "uint256"},
            {"indexed": False, "name": "fee",        "type": "uint256"},
        ],
        "name": "Withdrawn",
        "type": "event",
    },
]

# USDT BEP-20 ABI (transfer + balanceOf)
USDT_ABI = [
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "recipient", "type": "address"},
                   {"name": "amount",    "type": "uint256"}],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "spender", "type": "address"},
                   {"name": "amount",  "type": "uint256"}],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

# BSC USDT contract address (mainnet)
USDT_BSC_ADDRESS = "0x55d398326f99059fF775485246999027B3197955"
# BSC testnet USDT
USDT_BSC_TESTNET = "0x337610d27c682E347C9cD60BD4b3b107C9d34dDd"

SERVICE_FEE_BPS = 1500   # 15% in basis points


class EscrowContract:
    """
    Interface to the BSC escrow smart contract.
    Gracefully degrades to mock mode when Web3 is unavailable.
    """

    def __init__(self):
        self._w3 = None
        self._contract = None
        self._usdt = None
        self._account = None
        self._initialized = False
        self._mock_mode = False

        self.contract_address = os.getenv("ESCROW_CONTRACT_ADDRESS", "")
        self.bsc_rpc = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")
        self.private_key = os.getenv("BOT_WALLET_PRIVATE_KEY", "")
        self.service_wallet = os.getenv("SERVICE_WALLET_ADDRESS", "")
        self.usdt_address = os.getenv(
            "USDT_CONTRACT_ADDRESS",
            USDT_BSC_ADDRESS if os.getenv("BSC_NETWORK", "mainnet") == "mainnet"
            else USDT_BSC_TESTNET,
        )

    def initialize(self) -> bool:
        """Connect to BSC node and load contract. Returns True on success."""
        if self._initialized:
            return not self._mock_mode

        try:
            from web3 import Web3

            self._w3 = Web3(Web3.HTTPProvider(self.bsc_rpc, request_kwargs={"timeout": 10}))

            # web3 v7: PoA middleware inject (BSC needs this)
            try:
                from web3.middleware import ExtraDataToPOAMiddleware
                self._w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            except ImportError:
                try:
                    from web3.middleware import geth_poa_middleware
                    self._w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                except ImportError:
                    pass  # middleware optional

            if not self._w3.is_connected():
                raise ConnectionError(f"Cannot connect to BSC RPC: {self.bsc_rpc}")

            if self.contract_address:
                self._contract = self._w3.eth.contract(
                    address=Web3.to_checksum_address(self.contract_address),
                    abi=ESCROW_ABI,
                )

            self._usdt = self._w3.eth.contract(
                address=Web3.to_checksum_address(self.usdt_address),
                abi=USDT_ABI,
            )

            if self.private_key:
                self._account = self._w3.eth.account.from_key(self.private_key)

            self._initialized = True
            self._mock_mode = False
            logger.info(f"EscrowContract connected to BSC: {self.bsc_rpc}")
            return True

        except ImportError:
            logger.warning("web3 package not installed — EscrowContract in mock mode")
        except Exception as e:
            logger.warning(f"EscrowContract init failed: {e} — mock mode")

        self._initialized = True
        self._mock_mode = True
        return False

    # ── Balance ───────────────────────────────────────────────────────────────

    def get_usdt_balance(self, wallet_address: str) -> Decimal:
        """Return USDT balance of a wallet address in human-readable units."""
        if self._mock_mode or not self._w3:
            return Decimal("0")
        try:
            from web3 import Web3
            raw = self._usdt.functions.balanceOf(
                Web3.to_checksum_address(wallet_address)
            ).call()
            return Decimal(str(raw)) / Decimal("1e18")
        except Exception as e:
            logger.error(f"get_usdt_balance failed: {e}")
            return Decimal("0")

    def get_escrow_balance(self, wallet_address: str) -> Decimal:
        """Return user's balance held in the escrow contract."""
        if self._mock_mode or not self._contract:
            return Decimal("0")
        try:
            from web3 import Web3
            raw = self._contract.functions.balanceOf(
                Web3.to_checksum_address(wallet_address)
            ).call()
            return Decimal(str(raw)) / Decimal("1e18")
        except Exception as e:
            logger.error(f"get_escrow_balance failed: {e}")
            return Decimal("0")

    # ── Deposit ───────────────────────────────────────────────────────────────

    def generate_deposit_address(self, user_telegram_id: int) -> str:
        """
        Generate a deterministic deposit address for a user.
        In production: derive HD wallet address from master key + user_id.
        For now: return the bot's hot wallet address (user sends USDT here).
        """
        if self._account:
            return self._account.address
        # Fallback: return service wallet
        return self.service_wallet or "0x0000000000000000000000000000000000000000"

    def verify_deposit(self, tx_hash: str) -> Tuple[bool, Decimal, str]:
        """
        Verify a deposit transaction on BSC.
        Returns (success, amount_usdt, from_address).
        """
        if self._mock_mode or not self._w3:
            return False, Decimal("0"), ""
        try:
            receipt = self._w3.eth.get_transaction_receipt(tx_hash)
            if receipt is None or receipt["status"] != 1:
                return False, Decimal("0"), ""

            tx = self._w3.eth.get_transaction(tx_hash)
            from_addr = tx["from"]

            # Decode USDT transfer amount from logs
            amount = self._decode_usdt_transfer(receipt)
            return True, amount, from_addr
        except Exception as e:
            logger.error(f"verify_deposit failed: {e}")
            return False, Decimal("0"), ""

    def _decode_usdt_transfer(self, receipt) -> Decimal:
        """Decode USDT Transfer event from transaction receipt."""
        try:
            from web3 import Web3
            transfer_topic = Web3.keccak(text="Transfer(address,address,uint256)").hex()
            for log in receipt.get("logs", []):
                if (
                    log["address"].lower() == self.usdt_address.lower()
                    and log["topics"][0].hex() == transfer_topic
                ):
                    amount_raw = int(log["data"], 16)
                    return Decimal(str(amount_raw)) / Decimal("1e18")
        except Exception:
            pass
        return Decimal("0")

    # ── Withdrawal ────────────────────────────────────────────────────────────

    def withdraw(
        self,
        to_address: str,
        amount_usdt: Decimal,
    ) -> Tuple[bool, str, Decimal, Decimal]:
        """
        Trigger withdrawal from escrow contract.
        Contract automatically deducts 15% fee.

        Returns:
            (success, tx_hash, net_amount, fee_amount)
        """
        if self._mock_mode:
            fee = amount_usdt * Decimal("0.15")
            net = amount_usdt - fee
            mock_hash = f"0x{'0' * 64}"
            logger.info(f"[MOCK] Withdrawal: {amount_usdt} USDT → {to_address} net={net} fee={fee}")
            return True, mock_hash, net, fee

        if not self._contract or not self._account:
            return False, "", Decimal("0"), Decimal("0")

        try:
            from web3 import Web3
            amount_wei = int(amount_usdt * Decimal("1e18"))
            to_checksum = Web3.to_checksum_address(to_address)

            # Build transaction
            nonce = self._w3.eth.get_transaction_count(self._account.address)
            gas_price = self._w3.eth.gas_price

            tx = self._contract.functions.withdraw(amount_wei).build_transaction({
                "from": self._account.address,
                "nonce": nonce,
                "gas": 200000,
                "gasPrice": gas_price,
            })

            # Sign and send
            signed = self._w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self._w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt["status"] != 1:
                return False, tx_hash.hex(), Decimal("0"), Decimal("0")

            fee = amount_usdt * Decimal("0.15")
            net = amount_usdt - fee
            logger.info(f"Withdrawal tx: {tx_hash.hex()} net={net} fee={fee}")
            return True, tx_hash.hex(), net, fee

        except Exception as e:
            logger.error(f"withdraw failed: {e}", exc_info=True)
            return False, "", Decimal("0"), Decimal("0")

    def is_paused(self) -> bool:
        """Check if the escrow contract is paused."""
        if self._mock_mode or not self._contract:
            return False
        try:
            return self._contract.functions.paused().call()
        except Exception:
            return False

    @property
    def mock_mode(self) -> bool:
        return self._mock_mode


# Module-level singleton
escrow = EscrowContract()
