from typing import override
from collections.abc import Callable
from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState
)
from langgraph.graph import END
from langgraph.types import Command
from langgraph.prebuilt.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage


class ClarificationMiddlewareState(AgentState):
    pass


class ClarificationOuterMiddleware(AgentMiddleware[ClarificationMiddlewareState]):

    @override
    def wrap_tool_call(self, request: ToolCallRequest, handler: Callable[[ToolCallRequest], ToolMessage | Command]) -> ToolMessage | Command:

        if request.tool_call.get('name', '') != "ask_clarification":
            return handler(request)
        return self._handle_clarification(request)

    @override
    async def awrap_tool_call(self, request: ToolCallRequest, handler: Callable[[ToolCallRequest], ToolMessage | Command]) -> ToolMessage | Command:
        if request.tool_call.get('name', '') != "ask_clarification":
            return await handler(request)
        return self._handle_clarification(request)

    def _format_clarification_message(self, args: dict) -> str:
        # 格式化澄清问题
        question = args.get('question', '')
        clarification_type = args.get('clarification_type', 'missing_source')
        context = args.get('context', '')
        options = args.get('options', [])

        type_icons = {
            'missing_source': "❓",
            'ambiguous_requirement': "🤔",
        }
        icon = type_icons.get(clarification_type, "❓")

        message_parts = []
        if context:
            message_parts.append(f"{icon} {context}")
            message_parts.append(f'\n{question}')
        else:
            message_parts.append(f"{icon} {question}")

        if options:
            message_parts.append('')
            for index, option in enumerate(options, 1):
                message_parts.append(f"选项 {index}: {option}")

        return '\n'.join(message_parts)

    def _handle_clarification(self, request: ToolCallRequest) -> ToolMessage | Command:

        args = request.tool_call.get('args', {})
        content = self._format_clarification_message(args)

        tool_message = ToolMessage(
            content=content,
            tool_call_id=request.tool_call.get("id", ""),
            name='ask_clarification'
        )

        return Command(
            update={'messages': [tool_message]},
            goto=END
        )
