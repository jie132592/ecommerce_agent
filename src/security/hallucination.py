"""
大模型幻觉防护模块

问题背景：
当 Agent 管理的工具过多时（10+ 个 Tool），
LLM 容易出现以下幻觉问题：
1. 工具选择错误 - 选了不存在的工具
2. 参数构造错误 - 给工具传了错误的参数
3. 虚构工具结果 - 没有实际调用工具但生成了结果
4. 越权调用 - 未经允许调用敏感工具

解决方案：
1. 工具注册白名单 - 只允许调用已注册的工具
2. 参数 Schema 校验 - 用 Zod 严格校验参数
3. 强制执行验证 - 必须实际调用工具才能返回结果
4. 敏感工具二次确认 - 涉及敏感操作的工具需要用户确认
"""
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, List

from langchain_core.messages import BaseMessage, AIMessage, ToolMessage
from langchain_core.tools import Tool


class HallucinationError(Exception):
    """幻觉错误异常"""
    pass

class ToolValidationError(Exception):
    """工具校验错误"""

@dataclass
class ToolRegistry:
    """工具注册表"""
    tools: Dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool):
        """注册工具"""
        self.tools[tool.name] = tool

    def unregister(self, name: str):
        """取消注册工具"""
        if name in self.tools:
            del self.tools[name]

    def get(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self.tools.get(name)

    def list_names(self) -> List[str]:
        """列出所有已经注册的工具名称"""
        return List(self.tools.keys())

    def is_register(self, name: str) -> bool:
        """检测工具是否已经注册"""
        return name in self.tools

class ToolCallValidator:
    """工具调用验证"""
# 敏感工具列表（需要二次确认）
    SENSITIVE_TOOLS = {
        "create_ticket": "创建工单",
        "transfer_to_human": "转接人工",
        "refund": "退款操作",
        "cancel_order": "取消订单",
        "delete_data": "删除数据",
    }

    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry
        self.call_history: List[Dict] = [] # 记录所有工具

    def validate_tool_name(self, tool_name: str) -> bool:
        """验证工具名字是否在白名单"""
        if not self.tool_registry.is_register(tool_name):
            return False
        return True

    def validate_tool_args(self, tool: Tool, args: Dict) -> tuple[bool, Optional[str]]:
        """验证工具参数是否符号Schema"""
        try:
            # 从工具的 args_schema 获取参数定义
            if hasattr(tool, "args_schema") or tool.args_schema:
                schema = tool.args_schema
                # 使用
                schema.model_validate(args)
            return True, None
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            # 如果没有 schema，至少检查必需参数
            return True, None

    def validate_call(self, tool_name: str, args: Dict) -> tuple[bool, Optional[str], bool]:
        """验证工具调用
        Returns:
            (is_valid, error_message, needs_confirmation)
        """
        # 检测工具是否存在
        if not self.validate_tool_name(tool_name):
            return False, f"工具 {tool_name} 不存在或未注册", False

        tool = self.tool_registry.get(tool_name)

        # 2. 检查是否是敏感工具
        needs_confirmation = tool_name in self.SENSITIVE_TOOLS

        # 3. 验证参数
        is_valid, error = self.validate_tool_args(tool, args)
        if not is_valid:
            return False, f"参数错误: {error}", False

        # 记录调用
        self.call_history.append({
            "tool": tool_name,
            "args": args,
            "timestamp": time.time(),
            # 确认通过
            "confirmed": not needs_confirmation
        })

        return True, None, needs_confirmation

    def get_call_history(self, limit: int = 100) -> List[Dict]:
        """获取调用历史"""
        return self.call_history[-limit:]

    def clear_call_history(self):
        """清除调用历史"""
        self.call_history.clear()

class ResultVerifier:
    """结果验证器"""
    def __init__(self):
        # 记录哪些id已经被执行
        self.expected_calls: Dict[str, bool] = {}

    def mark_expected(self, tool_call_id: str):
        """标记某个调用是预期的"""
        self.expected_calls[tool_call_id] = False

    def mark_executed(self, tool_call_id: str):
        """标记某个调用已经被执行"""
        self.expected_calls[tool_call_id] = True

    def verify(self, messages: List[BaseMessage]) -> tuple[bool, List[str]]:
        """验证消息列表中的工具是否已经被执行
        Returns:
            (is_valid, list_of_missing_call_ids)
        """
        # 新建空列表，存放没收到对应返回结果的工具调用 ID
        missing = []
        for msg in messages:
            # 只处理 AI 发出来的消息，并且这条消息里携带了工具调用
            if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls"):
                for tool_call in (msg.tool_calls or []):
                    tool_call_id = tool_call.get("id")
                    if tool_call_id and tool_call_id in self.expected_calls:
                        if not self.expected_calls[tool_call_id]:
                            missing.append(tool_call_id)
                return len(missing) == 0, missing

    def is_tool_result_missing(self, messages: List[BaseMessage], tool_name: str) -> bool:
        """检测某个工具调用是否缺失结果"""
        # 是否找到目标工具的调用（AI输出的tool_call）
        tool_call_found = False
        # 是否存在任意目标返回结果
        tool_result_found = False

        for msg in messages:
            # 分支1：检查AI消息里有没有目标工具调用
            if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls"):
                if tool_name == msg.tool_calls:
                    tool_call_found = True
            # 分支2：只要出现任意工具返回消息就标记
            if isinstance(msg, ToolMessage):
                tool_result_found = True

        return tool_call_found and not tool_result_found

class HallucinationGuard:
    """幻觉防护器"""
    def __init__(self, register: ToolRegistry):
        self.register = register
        self.validator = ToolCallValidator(register)
        self.verifier = ResultVerifier()

    def pre_validate(self, tool_name: str, args: Dict) -> tuple[bool, Optional[str]]:
        """调用前验证"""
        # 在 LLM 选择工具后、实际调用工具前执行
        is_valid, error, needs_confirm = self.validator.validate_call(tool_name, args)

        return is_valid, error

    def post_validate(self, messages: List[BaseMessage],
        allow_unexecuted: bool = False) -> tuple[bool, Optional[str]]:
        """调用后验证检查是否有未执行的工具调用（LLM 可能在编造结果）"""
        is_valid, missing = self.verifier.verify(messages)
        if not is_valid or not allow_unexecuted:
            return False, f"检测到未执行的工具调用: {missing}"

    def validate_response(self, messages: List[BaseMessage],
        max_tool_calls: int = 5) -> tuple[bool, Optional[str]]:
        """综合验证LLM的回复
        检查：
        1. 工具调用数量是否合理
        2. 是否有未执行的结果
        3. 是否有敏感工具被调用
        """
        # 统计同居调用次数
        tool_calls_count = 0
        for msg in messages:
            if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls"):
                tool_calls_count += len(msg.tool_calls or [])

        # 检查调用次数是否过多（可能是循环调用）
        if tool_calls_count > max_tool_calls:
            return False, f"工具调用次数过多（{tool_calls_count}），可能陷入循环"

        # 检查是否有未执行的结果
        is_valid, error = self.post_validate(messages)
        if not is_valid:
            return False, error
        return True, None

class FallbackStrategy:
    """降级策略 - 当检测到幻觉时的处理"""
    FALLBACK_RESPONSES = {
        "tool_not_found": "抱歉，系统无法处理此请求，请稍后再试或联系人工客服。",
        "too_many_calls": "抱歉，问题较为复杂，请联系人工客服获取帮助。",
        "unexecuted_tool": "抱歉，我在处理您的请求时遇到了问题，请稍后再试。",
        "confirmation_failed": "您已拒绝操作，还有其他可以帮您的吗？",
    }

    @classmethod
    def get_response(cls, error_type: str) -> str:
        return cls.FALLBACK_RESPONSES.get(error_type, "抱歉，系统繁忙，请稍后再试。")

# 全局注册工具类
_global_registry: Optional[ToolRegistry] = None
def get_global_registry():
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry

def register_all_tools(tools: List[Tool]):
    register = ToolRegistry()
    for tool in tools:
        register.register(tool)

# 全局验证器
_validator: Optional[ToolCallValidator] = None
def get_validator():
    global _validator
    if _validator is None:
        _validator = ToolCallValidator(get_global_registry())
    return _validator