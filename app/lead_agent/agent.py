
from langchain.agents import create_agent

from langchain_core.runnables import RunnableConfig
from app.models.factory import create_chat_model


def make_lead_agent(config: RunnableConfig):
    return create_agent(
        model=create_chat_model('gpt-4')
    )
