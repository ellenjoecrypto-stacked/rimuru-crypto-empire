"""Automation Services — recurring task execution for income generation."""

from datetime import datetime


class AutomationServices:
    """Manages scheduled tasks: reward claims, rebalancing, compounding."""

    def __init__(self):
        self.tasks = []
        self.execution_log = []

    def register_task(self, name: str, interval_minutes: int, action: str) -> dict:
        task = {
            "name": name,
            "interval_minutes": interval_minutes,
            "action": action,
            "registered_at": datetime.utcnow().isoformat(),
            "last_run": None,
            "enabled": True,
        }
        self.tasks.append(task)
        return task

    def run_due_tasks(self) -> list:
        """Check and execute any tasks that are due."""
        results = []
        now = datetime.utcnow()
        for task in self.tasks:
            if not task["enabled"]:
                continue
            # TODO: real time-based scheduling check
            result = {
                "task": task["name"],
                "action": task["action"],
                "status": "simulated",
                "executed_at": now.isoformat(),
            }
            task["last_run"] = now.isoformat()
            self.execution_log.append(result)
            results.append(result)
        return results

    def get_task_report(self) -> dict:
        return {
            "total_tasks": len(self.tasks),
            "enabled": sum(1 for t in self.tasks if t["enabled"]),
            "executions": len(self.execution_log),
            "recent": self.execution_log[-5:],
        }
