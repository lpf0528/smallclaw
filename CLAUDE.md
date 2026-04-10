# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码库中工作时提供指导。

## 项目概述

SmallClaw 是一个多渠道 AI 智能体平台，将来自聊天平台（飞书）的消息路由到基于 LangGraph 的智能体，实现自然语言转 SQL（NL2SQL）的对话式查询。

## 开发命令

### 运行应用

```bash
# 启动 LangGraph 开发服务器（主要方式）
langgraph dev --allow-blocking --no-reload

# 启动 FastAPI 网关服务器
uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001
```

### 代码检查

```bash
flake8
```

配置：max-line-length=88，忽略 E501/E203/W503

### 包管理

使用 `uv` 进行依赖管理，需要 Python 3.12+。

```bash
uv sync
```

## 架构

### 三层并发模型

应用使用三个并发执行上下文：
1. **子线程**：飞书 WebSocket 客户端（阻塞式，独立事件循环）
2. **主线程**：FastAPI + asyncio 事件循环
3. **线程池**：通过 `asyncio.to_thread()` 执行阻塞式 SDK 调用

跨线程通信使用 `asyncio.run_coroutine_threadsafe()` 将任务从子线程安全地调度到主事件循环。

### 消息流转

```
飞书 WebSocket → MessageBus → ChannelManager → LangGraph Agent → OutboundMessage → 飞书 API
```

- `InboundMessage` 类型：CHAT（聊天）、COMMAND（命令）
- `OutboundMessage` 包含 `is_final` 标志用于流式响应
- 卡片消息通过原地更新实现流式效果

### 核心组件

| 目录 | 职责 |
|------|------|
| `app/channels/` | 渠道实现（feishu.py）、消息总线、会话存储 |
| `app/config/` | YAML 配置解析，支持环境变量解析（`$VAR` 语法） |
| `app/gateway/` | FastAPI 入口 |
| `app/lead_agent/` | LangGraph 智能体：图构建器、节点、提示词模板 |
| `app/models/` | LLM 工厂（ChatOpenAI） |
| `app/db/` | SQLAlchemy 引擎配置 |

### LangGraph 智能体图

定义于 `app/lead_agent/graph/builder.py`：
```
START → semantic_parser_node → schema_retriever_node → END
```

- `semantic_parser_node`：将自然语言转换为结构化 JSON
- `schema_retriever_node`：将 JSON 映射到数据库表

智能体入口：`app/lead_agent/agent.py:make_lead_agent`

### 配置文件

- `config.yaml`：模型、数据库、渠道、会话设置
- `.env`：API 密钥和密文（使用 `.env.example` 作为模板）
- `langgraph.json`：LangGraph 部署配置

YAML 中的环境变量使用 `$VARIABLE` 语法解析。

## 必需的环境变量

```
FEISHU_APP_ID, FEISHU_APP_SECRET  # 飞书机器人凭证
OPENAI_API_KEY, OPENAI_API_BASE_URL  # LLM 配置
LANGSMITH_API_KEY  # 可选：LangSmith 追踪
POSTGRES_*  # 可选：PostgreSQL（默认使用 SQLite）
```
