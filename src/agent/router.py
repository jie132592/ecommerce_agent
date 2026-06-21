"""
Router Agent — 意图分类 + 人工介入判断

职责：
1. LLM zero-shot 分类用户意图
2. 高风险意图（投诉/退款）直接转人工
3. 低置信度时保守决策（转人工）
"""
from langchain_core.messages import HumanMessage, AIMessage

from src.agent.state import AgentState
from src.llm import get_llm
from src.prompts import ROUTER


async def router_node(state: AgentState) -> AgentState:
    """路由节点：分类意图 + 判断人工介入"""
    history = state.get("messages", [])
    last_msg = ""
    for msg in reversed(history):
        if isinstance(msg, HumanMessage):
            # 找到第一条最新用户消息，直接跳出循环
            last_msg = msg.content
            break
    # 遍历完没找到任何用户提问，兜底处理
    if not last_msg:
        return {
            "intent": "unknown",  # 意图标记为未知
            "intent_confidence": 0.0,  # 置信度0
            "needs_human": True,  # 需要转人工
            "escalation_reason": "无法获取用户消息",  # 升级人工原因
        }

    # 获取大模型
    llm = get_llm()
    try:
        prompt_text = ROUTER.render(user_message=last_msg)
        print(f"[ROUTER DEBUG] Calling LLM with message: {last_msg}")
        response = await llm.ainvoke([
            HumanMessage(content=prompt_text)
        ])
        print(f"[ROUTER DEBUG] LLM response: {response.content}")
        # 拿到模型返回的意图文本，去除首尾空格并转小写统一格式
        intent = response.content.strip().lower()
        # LLM调用超时/报错，意图直接设为未知
    except Exception as e:
        print(f"[ROUTER ERROR] {e}")
        intent = "unknown"

    # 定义合法的6种意图集合
    valid_intents = {"order_query", "customer_info", "refund", "complaint", "general", "unknown"}
    # 如果模型输出不在合法列表里，统一修正为unknown
    if intent not in valid_intents:
        intent = "unknown"

    # 判断是否要转人工：投诉、退款、未知意图 全部走人工
    needs_human = intent in ("refund", "complaint", "unknown")
    # 每种转人工意图对应的备注说明
    escalation_reasons = {
        "complaint": "用户表达不满或投诉，人工处理更能保障服务质量",
        "refund": "退款/退货涉及金额，人工确认更安全",
        "unknown": "无法理解用户意图，需要人工确认",
    }
    # 更新全局状态，输出分类结果给后续节点使用
    print(f"[ROUTER DEBUG] intent={intent}, needs_human={needs_human}")
    return {
        "intent": intent,
        # 非未知意图置信度0.85，未知只有0.3（代表识别不准）
        "intent_confidence": 0.85 if intent != "unknown" else 0.3,
        "needs_human": needs_human,
        # 根据意图取出对应的人工升级原因，无匹配则为空字符串
        "escalation_reason": escalation_reasons.get(intent, ""),
    }