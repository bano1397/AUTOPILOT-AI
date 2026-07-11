"""Prompts for the supervisor's routing decision."""

from __future__ import annotations

from app.domain.interfaces.llm import ChatMessage, ChatRole

ROUTING_SYSTEM_PROMPT = (
    "You are a routing classifier for an AI assistant platform. Decide which "
    "specialist should handle the user's request and reply with EXACTLY one "
    "word:\n"
    "- knowledge: any factual question that could be answered from the user's "
    "stored documents — company policies, HR rules, benefits, contracts, "
    "invoices, reports, procedures, or specifics about their organization.\n"
    "- research: questions about the outside world that need current or public "
    "information from the web — companies, competitors, markets, news, "
    "technologies, prices, or anything explicitly asking to research or look up.\n"
    "- plan: requests to plan, organize, break down work, or create tasks or a "
    "todo list for a goal or project.\n"
    "- general: greetings, small talk, and requests that are clearly not "
    "answerable from stored documents or the web (creative writing, coding "
    "help, chit-chat).\n"
    "If you are unsure between knowledge and general, choose knowledge.\n"
    "Examples:\n"
    "'hi, how are you?' -> general\n"
    "'write me a haiku about spring' -> general\n"
    "'how many vacation days do employees get?' -> knowledge\n"
    "'what does the contract say about payment terms?' -> knowledge\n"
    "'do unused days roll over?' -> knowledge\n"
    "'research the main competitors of OpenAI' -> research\n"
    "'what is the latest LangGraph release?' -> research\n"
    "'plan the launch of our newsletter' -> plan\n"
    "'break down the website redesign into tasks' -> plan\n"
    "Reply with only the single word, nothing else."
)


def build_routing_messages(request: str) -> list[ChatMessage]:
    """Build the classification prompt for a user request."""
    return [
        ChatMessage(role=ChatRole.SYSTEM, content=ROUTING_SYSTEM_PROMPT),
        ChatMessage(role=ChatRole.USER, content=request),
    ]
