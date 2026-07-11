# Agent Development Guide

Agents are single-responsibility LangGraph nodes coordinated by the supervisor.
They communicate only through the shared `AgentState` — never by calling each
other directly.

## 1. Implement the contract

```python
# app/agents/weather/agent.py
from typing import ClassVar
from app.agents.base import BaseAgent
from app.platform.registry import register_agent
from app.workflows.state import AgentState

@register_agent
class WeatherAgent(BaseAgent):
    name: ClassVar[str] = "weather"
    description: ClassVar[str] = "Answers questions about the weather."

    def __init__(self, llm, recorder) -> None:   # inject the ports it needs
        self._llm = llm
        self._recorder = recorder

    async def run(self, state: AgentState) -> AgentState:
        result = await self._recorder.chat(
            self._llm, build_messages(state["request"]),
            feature="agent.weather", agent_name=self.name,
            user_id=UUID(state["user_id"]),
        )
        return {"agent": self.name, "answer": result.content,
                "grounded": False, "sources": [], "web_sources": []}
```

Key rules:
- Keep prompts in a sibling `prompts.py`, not inline.
- **Route every LLM call through `AiExecutionRecorder.chat(...)`** so it is
  audited (tokens, cost, duration, errors) and shows up in analytics.
- Return only the state slice you contribute; the executor merges it.

## 2. Register it in the graph

Add the agent to `AgentRunService.__init__` (`app/features/agents/service.py`)
and to the agents map passed to `build_agent_graph`. Its dependencies are wired
in `app/features/agents/dependencies.py`.

## 3. Teach the supervisor to route to it

- Add a route constant + branch in `app/agents/supervisor/supervisor.py`
  (`parse_route`, and `fast_route` if there is an unambiguous command verb).
- Add the class + an example to `ROUTING_SYSTEM_PROMPT` in
  `app/agents/supervisor/prompts.py`.

## 4. Test it

Script the fake LLM and assert routing, output, audit rows, and honest
degradation (see `tests/integration/test_research.py` for the pattern).

## Human-in-the-loop

Set `needs_approval` on the initial state to make a run pause at the approval
gate; the drafted answer is held until a decision resumes it from the
checkpoint. See `app/workflows/nodes.py` and the approvals feature.
