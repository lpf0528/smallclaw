from langchain_core.tools import tool
from typing import Annotated, Any, Literal


@tool("generate_sql", parse_docstring=True, return_direct=True)
def nl2sql_generate_sql_tool(
    sql: str,
    tables: list[str],
    chart_type: Literal["table", "column", "bar", "line", "pie"],
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
    - tables 必须列出 SQL 中实际用到的所有表名（去重）
    - chart_type 必须根据查询结构和数据形态选择最合适的类型

    ============================================================
    【chart_type 选择指南】
    ============================================================
    - table：原始数据展示、多指标场景、默认兜底
    - column：分类对比（纵向柱状图），如各班级的授权人数
    - bar：分类对比（横向条形图），类别名称较长时优先
    - line：时间趋势，需按时间维度排序
    - pie：占比分析，单维度单指标，类别数 ≤ 8

    Args:
        sql: 生成的 SELECT 查询语句。必须遵循 Apache Doris 语法，
            包含 LIMIT 子句，所有标识符加反引号，多表查询字段引用带表别名。
        tables: SQL 查询涉及的所有表名列表（不含数据库前缀，去重）。
            例如 ["dwd_lh_classes", "dim_lh_teaching_class_term"]
        chart_type: 推荐的图表展示类型。必须是以下之一（table、column、bar、line、pie）
    """
    # 实际逻辑由下游中间件处理
    # 中间件会解析参数、校验 SQL、执行查询并返回结果给用户
    return "SQL generation request processed by middleware"


@tool("ask_clarification", parse_docstring=True, return_direct=True)
def nl2sql_ask_clarification_tool(
    question: str,
    clarification_type: Literal[
        "missing_table",
        "missing_field",
        "unknown_enum_value",
        "ambiguous_metric"
    ],
    context: str | None = None,
    options: list[str] | None = None,
) -> str:
    """当你无法基于已有 schema 明确生成 SQL 时,向用户询问以获得澄清。

    ⚠️ 这是一个高门槛工具。在调用前,你必须确认无法通过 schema、terminologies、
    rules 中的默认行为自行解决问题。大多数"看起来需要澄清"的情况实际上不需要澄清。

    ============================================================
    【何时调用】仅在以下四种情况下调用:
    ============================================================

    - **缺少数据表 (missing_table)**: 用户提问涉及的业务对象在 schema 中找不到对应表
      例如用户问"支付流水"但 schema 中无订单/流水表

    - **缺少字段 (missing_field)**: 表存在但所需字段未定义
      例如用户问"学员手机号"但学员表中无 phone 字段

    - **枚举值不明 (unknown_enum_value)**: 过滤条件涉及的字段枚举值未在 schema 中列出
      例如用户说"已完成的营期"但 state 字段的 enum 中未列出"已完成"对应的值
      ⚠️ 严格限制:仅当【用户主动提到了某个状态/类别】且【该字段未声明 default_filter】
         且【该枚举值在 schema 的 enum 中找不到对应项】时才使用此类型

    - **指标多义 (ambiguous_metric)**: 查询主体存在多种可能的字段映射
      例如"人数"可能指 original_num / new_original_num / authorize_num
      ⚠️ 必须通过 options 参数提供候选字段列表

    ============================================================
    【禁止调用】以下情况严禁调用本工具,必须直接生成 SQL:
    ============================================================

    ❌ 用户提问中根本没提到的维度,不要主动追问
       反例: 用户问"第37期有多少个班级",禁止追问"需要哪种状态的班级?"
       原因: 用户根本没提"状态",这是模型自己加戏

    ❌ 字段在 schema 中已声明 default_filter 属性的,直接套用,不要追问
       反例: dwd_lh_classes.state 已有 default_filter="normal",
            禁止追问"需要查看正常还是已删除的班级?"

    ❌ 业务术语在 terminologies 中已有 mapping 的,直接套用,不要追问
       反例: terminologies 已定义"第N期 → rank=N",
            禁止追问"第37期的营期 ID 是否为 37?"

    ❌ rules 中已有强制默认行为的项目,不要追问
       反例: 数据量限制规则强制 LIMIT 1000,
            禁止追问"是否需要限制返回的记录数?"

    ❌ 时间排序、时间格式等已有默认规则的,不要追问

    ============================================================
    【调用前自检清单】调用工具前,逐项回答以下问题:
    ============================================================

    1. 我打算澄清的内容,是否在用户原始提问中被明确提到了?
       (如果用户根本没提,不要调用)
    2. 我打算澄清的字段,是否已声明 default_filter 属性?
       (如果有,不要调用)
    3. 我打算澄清的术语,是否在 terminologies 中已有 mapping?
       (如果有,不要调用)
    4. 我打算澄清的内容,是否在 rules 中已有强制默认行为?
       (如果有,不要调用)
    5. 我能否在不损失正确性的前提下,使用合理的默认值生成 SQL?
       (如果能,不要调用)

    任意一项的答案让本次澄清变得不必要,则【禁止调用】,必须直接生成 SQL。

    ============================================================
    【调用后行为】
    ============================================================
    - 调用后,执行流程会被自动中断,问题会呈现给用户
    - 在用户回复之前请勿继续执行
    - 不要在调用此工具的同一轮中再返回 success 结果
    - 不要带着假设继续生成 SQL

    ============================================================
    【最佳实践】
    ============================================================
    - 每次只问一个澄清问题,保持清晰
    - 问题要具体、明确,直接指向 schema 中缺失或歧义的部分
    - 对于 ambiguous_metric,必须通过 options 提供候选字段供用户选择
    - 对于 missing_table / missing_field,在 question 中明确告知 schema 边界

    Args:
        question: 要向用户提出的澄清问题。需具体且清晰,直接指向 schema 中缺失或歧义的部分。禁止包含用户原始提问中未提到的维度。
        clarification_type: 澄清类型,必须是以下之一:（missing_table、missing_field、unknown_enum_value、ambiguous_metric）
        context: 可选的上下文,用于说明为何需要澄清。建议包含已识别到的相关表/字段,帮助用户理解当前 schema 的边界。
        options: 可选的选项列表。在 ambiguous_metric 类型时【必须】提供,列出 schema 中所有可能匹配的字段及其业务含义,供用户选择。
    """
    # 实际逻辑由 ClarificationMiddleware 处理,它会拦截此工具调用
    # 并中断执行,将问题呈现给用户
    return "Clarification request processed by middleware"
