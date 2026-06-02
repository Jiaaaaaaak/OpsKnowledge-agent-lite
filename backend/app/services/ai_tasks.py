from __future__ import annotations

from typing import Literal

AgentTask = Literal["classify", "severity", "insights", "action_items"]

AGENT_TASK_CLASSIFY: AgentTask = "classify"
AGENT_TASK_SEVERITY: AgentTask = "severity"
AGENT_TASK_INSIGHTS: AgentTask = "insights"
AGENT_TASK_ACTION_ITEMS: AgentTask = "action_items"


def agent_task_marker(task: AgentTask) -> str:
    return f"<<AGENT_TASK:{task}>>"
