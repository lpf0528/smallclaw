

from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from app.models.factory import create_chat_model
from app.agents.prompts.template import get_system_prompt_template
from app.agents.nl2sql_agent.thread_state import ThreadState
from app.agents.nl2sql_agent.tools import nl2sql_generate_sql_tool, nl2sql_ask_clarification_tool


def get_available_tools():
    return [nl2sql_generate_sql_tool, nl2sql_ask_clarification_tool]


def make_nl2sql_agent(config: RunnableConfig):

    return create_agent(
        model=create_chat_model('gpt-4'),
        tools=get_available_tools(),
        # middleware=[],
        system_prompt=get_system_prompt_template("NL2SQL_AGENT_SYSTEM_PROMPT.xml"),
        state_schema=ThreadState,
    )
