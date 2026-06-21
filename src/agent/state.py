"""
Agent 共享状态定义

多 Agent 协作时，所有 Agent 共享同一份状态，
每个 Agent 只负责修改自己相关的字段。
"""

from typing import Annotated, Sequence, TypedDict
import operator
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """多 Agent 共享状态"""

    # 对话历史（所有 Agent 的输出都 append 到这里）
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # 用户信息
    user_id: str
    session_id: str

    # ======= Router Agent 填充 =======
    intent: str  # 意图分类：order_query | refund | complaint | general | unknown
    intent_confidence: float  # 置信度 0~1，低于阈值触发人工

    # ======= Planner / Executor 填充 =======
    plan: str  # 执行计划描述
    needs_human: bool  # 是否需要人工介入
    escalation_reason: str  # 转人工原因

    # ========= Reviewer 填充 =======
    reflection_score: float  # 回答质量评分 0~1
    reflection_reason: str  # 评分理由
    needs_revision: bool  # 是否需要重做
