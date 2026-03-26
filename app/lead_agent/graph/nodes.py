from typing import Any, Dict

from langgraph.runtime import Runtime
from app.lead_agent.graph.types import State
from typing_extensions import TypedDict
from app.lead_agent.prompts.template import get_system_prompt_template
from langchain.agents import create_agent
from app.db.table_definitions import TABLE_CATALOG


def semantic_parser_node(state: State, runtime: Runtime[TypedDict]) -> Dict[str, Any]:
    """将用户自然语言问题解析为结构化语义 JSON。
    """
    system_prompt = get_system_prompt_template("SEMANTIC_PARSE_PROMPT", state)

    agent = create_agent(
        model="gpt-4o-mini",
        system_prompt=system_prompt,
    )

    response = agent.invoke(
        {"messages": [{"role": "user", "content": state["question"]}]}
    )
    return {'messages': response["messages"],
            "semantic": response["messages"][-1].content
            }


def schema_retriever_node(state: State, runtime: Runtime[TypedDict]) -> Dict[str, Any]:
    """根据语义 JSON 从表目录中选出查询所需的最小表集合，返回表名列表
    """

    table_catalog = "\n".join(
        f"- {name}: {desc}"
        for name, desc in TABLE_CATALOG.items()
    )

    system_prompt = get_system_prompt_template("TABLE_SELECTOR_PROMPT", state, table_catalog=table_catalog)

    messages = [
        {
            "role": "human",
            "content": f"查询语义：\n{state['semantic']}",
        }
    ]

    agent = create_agent(
        model="gpt-4o-mini",
        system_prompt=system_prompt,
    )

    response = agent.invoke(
        {"messages": messages}
    )
    return {'messages': response["messages"]}
