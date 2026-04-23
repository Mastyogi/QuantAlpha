"""Run codebase audit."""
import asyncio
from src.audit.audit_engine import CodebaseAuditor

async def main():
    auditor = CodebaseAuditor(root_dir="src")
    report = await auditor.generate_report("audit_report.md")
    print(f"Audit complete! Report saved to audit_report.md")
    print(f"Found {len(report.identified_gaps)} gaps")
    print(f"Generated {len(report.recommendations)} recommendations")

if __name__ == "__main__":
    asyncio.run(main())
