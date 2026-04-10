from typing import Annotated, Any, Literal
from langchain.tools import InjectedToolCallId, ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from langgraph.typing import ContextT
from app.agents.nl2sql_agent.thread_state import ThreadState


@tool("retrieve_database_table", parse_docstring=True)
def retrieve_database_table_tool(
    runtime: ToolRuntime[ContextT, ThreadState],
    tables: list[str],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Query and retrieve field/schema information for the specified database tables.

    Use this tool when you need to inspect the structure (columns, types, constraints)
    of one or more database tables before constructing SQL queries.

    Args:
        tables: A list of table names to retrieve schema information for.
            Must be non-empty. Example: ["users", "orders"].

    Returns:
        A command that updates the conversation state with the retrieval result.
    """
    # 参数校验
    if not tables:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        "Error: `tables` must contain at least one table name.",
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ],
            },
        )

    # 去重并保持顺序
    unique_tables = list(dict.fromkeys(tables))

    try:
        # ... 实际的表结构查询逻辑 ...
        # schemas = fetch_table_schemas(unique_tables)
        pass
    except Exception as e:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Failed to retrieve tables {unique_tables}: {e}",
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ],
            },
        )

    return Command(
        update={
            "messages": [
                ToolMessage(
                    f"Successfully retrieved schema for {len(unique_tables)} "
                    f"table(s): {', '.join(unique_tables)}.",
                    tool_call_id=tool_call_id,
                    status="success",
                )
            ],
        },
    )
