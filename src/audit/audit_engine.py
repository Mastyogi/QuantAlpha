"""
Codebase Audit Engine
Comprehensive analysis of trading bot codebase for improvement identification.
"""

import os
import ast
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Gap:
    """Identified capability gap."""
    category: str
    description: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    current_state: str
    target_state: str
    estimated_effort: str  # SMALL, MEDIUM, LARGE


@dataclass
class Recommendation:
    """Improvement recommendation."""
    title: str
    description: str
    priority: int  # 1-5, 1 being highest
    category: str
    estimated_hours: int
    dependencies: List[str] = field(default_factory=list)


@dataclass
class AuditReport:
    """Complete audit report."""
    timestamp: str
    structure_summary: Dict
    quality_metrics: Dict
    identified_gaps: List[Gap]
    recommendations: List[Recommendation]
    priority_matrix: Dict
    
    def save(self, path: str):
        """Save report as markdown."""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self._generate_markdown())
        logger.info(f"Audit report saved to {path}")
    
    def _generate_markdown(self) -> str:
        """Generate markdown report."""
        md = f"""# Trading Bot Codebase Audit Report

**Generated**: {self.timestamp}

## Executive Summary

This audit analyzes the trading bot codebase to identify strengths, weaknesses, and improvement opportunities for transforming it into a self-improving portfolio fund compounder.

## 1. Structure Analysis

### Directory Structure
"""
        # Structure summary
        for key, value in self.structure_summary.items():
            md += f"- **{key}**: {value}\n"
        
        md += "\n## 2. Quality Metrics\n\n"
        
        # Quality metrics
        for metric, value in self.quality_metrics.items():
            md += f"- **{metric}**: {value}\n"
        
        md += "\n## 3. Identified Gaps\n\n"
        
        # Gaps by severity
        for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            gaps = [g for g in self.identified_gaps if g.severity == severity]
            if gaps:
                md += f"### {severity} Priority Gaps\n\n"
                for gap in gaps:
                    md += f"#### {gap.category}\n"
                    md += f"- **Description**: {gap.description}\n"
                    md += f"- **Current State**: {gap.current_state}\n"
                    md += f"- **Target State**: {gap.target_state}\n"
                    md += f"- **Estimated Effort**: {gap.estimated_effort}\n\n"
        
        md += "\n## 4. Recommendations\n\n"
        
        # Recommendations by priority
        sorted_recs = sorted(self.recommendations, key=lambda r: r.priority)
        for rec in sorted_recs:
            md += f"### Priority {rec.priority}: {rec.title}\n"
            md += f"- **Category**: {rec.category}\n"
            md += f"- **Description**: {rec.description}\n"
            md += f"- **Estimated Hours**: {rec.estimated_hours}\n"
            if rec.dependencies:
                md += f"- **Dependencies**: {', '.join(rec.dependencies)}\n"
            md += "\n"
        
        md += "\n## 5. Priority Matrix\n\n"
        
        # Priority matrix
        for category, items in self.priority_matrix.items():
            md += f"### {category}\n"
            for item in items:
                md += f"- {item}\n"
            md += "\n"
        
        md += "\n## Conclusion\n\n"
        md += "This audit provides a comprehensive analysis of the current codebase and a roadmap for transformation into a self-improving portfolio fund compounder.\n"
        
        return md


class StructureAnalyzer:
    """Analyzes directory structure and module organization."""
    
    def analyze(self, root_dir: str) -> Dict:
        """Analyze codebase structure."""
        logger.info(f"Analyzing structure of {root_dir}")
        
        structure = {
            "total_files": 0,
            "total_lines": 0,
            "python_files": 0,
            "modules": [],
            "components": {},
        }
        
        root_path = Path(root_dir)
        
        for py_file in root_path.rglob("*.py"):
            if "__pycache__" in str(py_file) or "migrations" in str(py_file):
                continue
            
            structure["python_files"] += 1
            structure["total_files"] += 1
            
            # Count lines
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    lines = len(f.readlines())
                    structure["total_lines"] += lines
            except Exception as e:
                logger.warning(f"Could not read {py_file}: {e}")
            
            # Identify module
            relative_path = py_file.relative_to(root_path)
            module_name = str(relative_path.parent).replace(os.sep, '.')
            
            if module_name not in structure["modules"]:
                structure["modules"].append(module_name)
            
            # Categorize components
            if "agents" in str(py_file):
                structure["components"]["agents"] = structure["components"].get("agents", 0) + 1
            elif "ai_engine" in str(py_file):
                structure["components"]["ai_engine"] = structure["components"].get("ai_engine", 0) + 1
            elif "risk" in str(py_file):
                structure["components"]["risk"] = structure["components"].get("risk", 0) + 1
            elif "execution" in str(py_file):
                structure["components"]["execution"] = structure["components"].get("execution", 0) + 1
            elif "signals" in str(py_file):
                structure["components"]["signals"] = structure["components"].get("signals", 0) + 1
            elif "strategies" in str(py_file):
                structure["components"]["strategies"] = structure["components"].get("strategies", 0) + 1
            elif "data" in str(py_file):
                structure["components"]["data"] = structure["components"].get("data", 0) + 1
            elif "telegram" in str(py_file):
                structure["components"]["telegram"] = structure["components"].get("telegram", 0) + 1
            elif "database" in str(py_file):
                structure["components"]["database"] = structure["components"].get("database", 0) + 1
        
        logger.info(f"Structure analysis complete: {structure['python_files']} Python files, {structure['total_lines']} lines")
        return structure


class QualityAnalyzer:
    """Evaluates code quality metrics."""
    
    def analyze(self, root_dir: str) -> Dict:
        """Analyze code quality."""
        logger.info(f"Analyzing code quality of {root_dir}")
        
        quality = {
            "total_functions": 0,
            "total_classes": 0,
            "avg_function_length": 0,
            "avg_class_length": 0,
            "docstring_coverage": 0.0,
            "test_coverage": "Unknown (requires pytest-cov)",
            "complexity_score": "Medium",
        }
        
        root_path = Path(root_dir)
        function_lengths = []
        class_lengths = []
        functions_with_docstrings = 0
        
        for py_file in root_path.rglob("*.py"):
            if "__pycache__" in str(py_file) or "migrations" in str(py_file):
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read(), filename=str(py_file))
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        quality["total_functions"] += 1
                        func_length = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                        function_lengths.append(func_length)
                        
                        if ast.get_docstring(node):
                            functions_with_docstrings += 1
                    
                    elif isinstance(node, ast.ClassDef):
                        quality["total_classes"] += 1
                        class_length = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                        class_lengths.append(class_length)
            
            except Exception as e:
                logger.warning(f"Could not parse {py_file}: {e}")
        
        # Calculate averages
        if function_lengths:
            quality["avg_function_length"] = sum(function_lengths) / len(function_lengths)
        if class_lengths:
            quality["avg_class_length"] = sum(class_lengths) / len(class_lengths)
        
        # Docstring coverage
        if quality["total_functions"] > 0:
            quality["docstring_coverage"] = (functions_with_docstrings / quality["total_functions"]) * 100
        
        logger.info(f"Quality analysis complete: {quality['total_functions']} functions, {quality['total_classes']} classes")
        return quality


class GapAnalyzer:
    """Compares current vs target capabilities."""
    
    def analyze(self, structure: Dict, requirements: List[str]) -> List[Gap]:
        """Identify capability gaps."""
        logger.info("Analyzing capability gaps")
        
        gaps = []
        
        # Check for self-improvement components
        if "ml" not in structure.get("components", {}):
            gaps.append(Gap(
                category="Self-Improvement Engine",
                description="No self-improvement or continuous learning infrastructure found",
                severity="CRITICAL",
                current_state="Manual model training only",
                target_state="Automated daily analysis and weekly retraining",
                estimated_effort="LARGE"
            ))
        
        # Check for pattern library
        if "pattern" not in str(structure.get("modules", [])).lower():
            gaps.append(Gap(
                category="Pattern Library",
                description="No pattern storage or strategy discovery system",
                severity="HIGH",
                current_state="No pattern persistence",
                target_state="Database-backed pattern library with validation",
                estimated_effort="MEDIUM"
            ))
        
        # Check for approval system
        if "approval" not in str(structure.get("modules", [])).lower():
            gaps.append(Gap(
                category="Approval System",
                description="No approval workflow for model updates",
                severity="HIGH",
                current_state="Direct deployment without approval",
                target_state="Telegram-based approval workflow",
                estimated_effort="MEDIUM"
            ))
        
        # Check for portfolio compounding
        if "compounder" not in str(structure.get("modules", [])).lower():
            gaps.append(Gap(
                category="Portfolio Compounding",
                description="No Kelly Criterion or compounding position sizing",
                severity="HIGH",
                current_state="Fixed position sizing",
                target_state="Kelly Criterion with equity-based scaling",
                estimated_effort="MEDIUM"
            ))
        
        # Check for profit booking engine
        if "profit_booking" not in str(structure.get("modules", [])).lower():
            gaps.append(Gap(
                category="Profit Booking Engine",
                description="No multi-tier take-profit system",
                severity="MEDIUM",
                current_state="Single take-profit level",
                target_state="3-tier TP with trailing stops",
                estimated_effort="MEDIUM"
            ))
        
        # Check for auto-tuning
        if "auto_tuning" not in str(structure.get("modules", [])).lower() and "optuna" not in str(structure.get("modules", [])).lower():
            gaps.append(Gap(
                category="Auto-Tuning System",
                description="No hyperparameter optimization system",
                severity="MEDIUM",
                current_state="Manual parameter tuning",
                target_state="Optuna-based auto-tuning triggered by performance",
                estimated_effort="LARGE"
            ))
        
        # Check for audit system
        if "audit" not in structure.get("components", {}):
            gaps.append(Gap(
                category="Audit System",
                description="No codebase audit or analysis system",
                severity="LOW",
                current_state="No automated audit capability",
                target_state="Comprehensive audit engine",
                estimated_effort="SMALL"
            ))
        
        logger.info(f"Gap analysis complete: {len(gaps)} gaps identified")
        return gaps


class ReportGenerator:
    """Generates markdown audit reports."""
    
    def generate(
        self,
        structure: Dict,
        quality: Dict,
        gaps: List[Gap]
    ) -> AuditReport:
        """Generate comprehensive audit report."""
        logger.info("Generating audit report")
        
        # Generate recommendations from gaps
        recommendations = []
        for i, gap in enumerate(gaps, 1):
            effort_hours = {
                "SMALL": 20,
                "MEDIUM": 40,
                "LARGE": 80
            }.get(gap.estimated_effort, 40)
            
            priority = {
                "CRITICAL": 1,
                "HIGH": 2,
                "MEDIUM": 3,
                "LOW": 4
            }.get(gap.severity, 3)
            
            recommendations.append(Recommendation(
                title=f"Implement {gap.category}",
                description=gap.description,
                priority=priority,
                category=gap.category,
                estimated_hours=effort_hours,
                dependencies=[]
            ))
        
        # Create priority matrix
        priority_matrix = {
            "Critical (Immediate)": [g.category for g in gaps if g.severity == "CRITICAL"],
            "High (This Sprint)": [g.category for g in gaps if g.severity == "HIGH"],
            "Medium (Next Sprint)": [g.category for g in gaps if g.severity == "MEDIUM"],
            "Low (Backlog)": [g.category for g in gaps if g.severity == "LOW"],
        }
        
        report = AuditReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            structure_summary=structure,
            quality_metrics=quality,
            identified_gaps=gaps,
            recommendations=recommendations,
            priority_matrix=priority_matrix
        )
        
        logger.info("Audit report generated successfully")
        return report


class CodebaseAuditor:
    """Main audit orchestrator."""
    
    def __init__(self, root_dir: str = "src"):
        self.root_dir = root_dir
        self.structure_analyzer = StructureAnalyzer()
        self.quality_analyzer = QualityAnalyzer()
        self.gap_analyzer = GapAnalyzer()
        self.report_generator = ReportGenerator()
    
    async def run_full_audit(self) -> AuditReport:
        """Execute complete codebase audit."""
        logger.info(f"Starting full audit of {self.root_dir}")
        
        # Analyze structure
        structure = self.structure_analyzer.analyze(self.root_dir)
        
        # Analyze quality
        quality = self.quality_analyzer.analyze(self.root_dir)
        
        # Identify gaps
        gaps = self.gap_analyzer.analyze(structure, [])
        
        # Generate report
        report = self.report_generator.generate(structure, quality, gaps)
        
        logger.info("Full audit complete")
        return report
    
    async def generate_report(self, output_path: str = "audit_report.md") -> AuditReport:
        """Generate and save audit report."""
        report = await self.run_full_audit()
        report.save(output_path)
        return report
