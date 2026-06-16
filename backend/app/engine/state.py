"""Shared graph state for the per-agent execution engine."""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    agent_slug: str
    selected_skill: str | None
    recalled: list[str]  # memory snippets injected into context
