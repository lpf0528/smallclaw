from langchain_core.tools import tool
from typing import Annotated, Any, Literal


@tool("generate_sql", parse_docstring=True)
def nl2sql_generate_sql_tool(
    sql: str,
    tables: list[str],
) -> str:
    """当你已经基于 schema 成功生成 SQL 查询时，调用此工具返回结果。

    这是 NL2SQL Agent 成功路径的唯一输出方式。禁止在自然语言回复中直接
    输出 SQL 内容——所有成功生成的 SQL 必须通过此工具返回，以便下游系统
    正确解析和执行。

    ============================================================
    【何时调用】
    ============================================================
    - 用户提问可以明确映射到 schema 中已有的表和字段
    - 提问无歧义，或歧义已通过 terminologies 消解
    - 已应用所有 rules 中定义的强制默认行为（LIMIT、状态过滤、时间排序等）
    - 已通过 ask_clarification 工具的前置检查清单（确认不需要澄清）

    ============================================================
    【禁止调用】
    ============================================================
    ❌ 需要向用户澄清时（应改为调用 ask_clarification）
    ❌ 简单闲聊、问候、拒绝等场景（应使用自然语言直接回复，不调用工具）
    ❌ SQL 未遵循 rules 中的强制规则时（必须先修正再调用）
    ❌ 包含非 SELECT 操作（DDL/DCL/INSERT/UPDATE/DELETE）时

    ============================================================
    【参数要求】
    ============================================================
    - sql 必须是合法的 Apache Doris SELECT 语句
    - sql 必须包含 LIMIT 子句（默认 1000）
    - sql 所有标识符必须加反引号
    - sql 多表查询所有字段引用必须带表别名
    - tables 必须列出 SQL 中实际用到的所有表名（去重，不含数据库前缀）

    Args:
        sql: 生成的 SELECT 查询语句。必须遵循 Apache Doris 语法，
            包含 LIMIT 子句，所有标识符加反引号，多表查询字段引用带表别名。
        tables: SQL 查询涉及的所有表名列表（不含数据库前缀，去重）。
            例如 ["dwd_lh_classes", "dim_lh_teaching_class_term"]
    """
    # 实际逻辑由下游中间件处理
    # 中间件会解析参数、校验 SQL、执行查询并返回结果给用户
    return "SQL generation request processed by middleware"
