
from langchain.agents import create_agent

from langchain_core.runnables import RunnableConfig
from app.models.factory import create_chat_model
from app.agents.prompts.template import get_system_prompt_template
from app.agents.tools.tools import get_available_tools
from app.agents.middlewares.clarification_middleware import ClarificationOuterMiddleware


def make_socra_agent(config: RunnableConfig):
    # Socra来自苏格拉底（Socrates）——他的教学法就是不断追问直到你真正理解。简短、有哲学底蕴，和 Agent 的「诊断式追问」高度吻合。
    # https://reference.langchain.com/python/deepagents

    return create_agent(
        model=create_chat_model('gpt-4'),
        tools=get_available_tools(),
        middleware=[ClarificationOuterMiddleware()],
        system_prompt=get_system_prompt_template("SOCRA_AGENT_SYSTEM_PROMPT")
    )
