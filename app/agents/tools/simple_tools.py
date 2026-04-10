from langchain_core.tools import tool
from typing import Annotated, Any, Literal


@tool("direct_response")
def direct_response_tool(
    message: Annotated[str, "The response message to send directly to user."],
    locale: Annotated[str, "The user's detected language locale (e.g., en-US, zh-CN)."],
):
    """Respond directly to user for greetings, small talk, or polite rejections. """
    # This tool is not returning anything: we're just using it
    # as a way for LLM to signal that it needs to directly respond
    return


@tool("ask_clarification")
def ask_clarification_tool(
    question: Annotated[str, "The question to ask the user."],
):
    """Ask the user a question to clarify the topic."""
    return
