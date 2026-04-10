
from langchain.agents import create_agent

from langchain_core.runnables import RunnableConfig
from app.models.factory import create_chat_model
from app.agents.prompts.template import get_system_prompt_template


def make_lead_agent(config: RunnableConfig):
    # https://reference.langchain.com/python/deepagents
    return create_agent(
        model=create_chat_model('gpt-4'),
        system_prompt=get_system_prompt_template("LEAD_AGENT_SYSTEM_PROMPT")
    )
