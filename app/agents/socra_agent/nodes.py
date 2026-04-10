import logging
from typing import Literal
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from langchain_core.messages import AIMessage
from app.models.factory import create_chat_model
from app.agents.socra_agent.tools import get_available_tools
from app.agents.socra_agent.types import State
from app.agents.prompts.template import get_system_prompt_template

logger = logging.getLogger(__name__)


def coordinator_node(state: State, config: RunnableConfig) -> Command[Literal["__end__"]]:
    """协调节点，负责协调其他节点的执行。
    """
    logger.info("Coordinator Node: Start")
    system_prompt = get_system_prompt_template("SOCRA_AGENT_SYSTEM_PROMPT", state)

    messages = [{"role": "system", "content": system_prompt}] + state["messages"]
    tools = get_available_tools()
    agent = create_chat_model(
        model="gpt-4o-mini",
        system_prompt=system_prompt,
    ).bind_tools(tools)
    goto = "__end__"
    response = agent.invoke(messages)
    locale = state.get('locale', 'zh-CN')
    if response.tool_calls:
        for tool_call in response.tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            if tool_name == "direct_response":
                reply = tool_args.get("message", "")
                locale = tool_args.get("locale", locale)
                goto = "__end__"
                messages.append(AIMessage(content=reply, name=tool_name))
            elif tool_name == "ask_clarification":
                question = tool_args.get("question", "")
                messages.append(AIMessage(content=question, name=tool_name))
            logger.info(f"Coordinator Node: Tool call: {tool_name} with args: {tool_args}")

    return Command(update={
        'locale': locale,
        'messages': messages,
    }, goto=goto)
