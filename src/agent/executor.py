"""
Executor Agent — 执行计划 + 工具调用

职责：
1. 根据意图制定执行计划（Plan）
2. 按计划调用相应工具
3. 返回执行结果给 Reviewer


- Plan-Act 分离：先规划再执行，避免 LLM 随机发挥
- 工具调用结果作为上下文传回，不丢失中间步骤
- 单轮多工具调用（asyncio.gather 并行）
- 模型路由：小模型处理简单规划，大模型处理复杂规划
"""
import asyncio
from typing import List

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI

from src.agent.state import AgentState
from src.config import LOCAL_LARGE_MODEL
from src.llm import get_llm, get_model_router
from src.prompts import PLANNER
from src.tools import get_customer_info, query_orders, get_order_status, search_knowledge_base, create_ticket, \
    transfer_to_human

ALL_TOOLS = [
    get_customer_info,
    query_orders,
    get_order_status,
    search_knowledge_base,
    create_ticket,
    transfer_to_human,
]

PLANNER_PROMPT = """你是一个客服任务规划助手。

根据用户意图，制定简洁的执行计划：
1. 明确要查什么信息
2. 明确按什么顺序调用工具
3. 如果信息足够直接回答，就不需要调用工具

回复格式（只输出计划，不要解释）：
plan: [你的执行计划，一句话描述]
tools: [需要的工具列表，用逗号分隔，可为空]
"""

async def _planner(llm: ChatOpenAI, intent: str, history_context: str) -> tuple[str, List[str]]:
    """指定执行计划"""
    # 渲染模板，填充意图+历史对话，封装成AI消息传给大模型
    messages = [
        AIMessage(content=PLANNER.render(intent=intent, history_context=history_context))
    ]
    try:
        # 异步调用LLM生成执行方案
        res = await llm.ainvoke(messages)
        content = res.content
        # 初始化变量：计划文本、需要调用的工具数组
        plan = ""
        tools_needed = []
        # 按换行分割模型返回文本，逐行解析固定格式
        for line in content.split('\n'):
            # 提取plan字段内容
            if line.startswith("plan:"):
                plan = line[:5].strip()
            # 提取tools工具名称列表
            elif line.startswith("tools:"):
                tool_names = line[:6].strip()
                # 不为空就按逗号切割，清理空格存入列表
                if tool_names:
                    tools_needed = [t.strip() for t in tool_names.split(",")]
        # 解析成功返回计划+工具列表，计划为空则默认直接回复用户
        return plan or "直接回复用户", tools_needed
    except Exception as e:
        return "直接回复用户", []

# 内部工具执行子函数：并行批量调用多个工具，返回每条工具结果封装的AI消息
async def _execute_tools(tool_names: List[str], user_id: str, session_id: str) -> List[AIMessage]:
    """并行执行多个工具"""
    # 无工具需要调用，直接返回空列表
    if not tool_names:
        return []
    # 构建映射：工具名字符串 → 工具函数对象
    tool_map = {t.name: t for t in ALL_TOOLS}

    #  过滤掉不存在、未注册的工具名，只保留有效工具函数
    valid_tools = [tool_map[name] for name in tool_names if name in tool_map]
    # 单个工具执行内部封装函数
    async def call_one(tool):
        try:
            if tool.name == "get_customer_info":
                result = await tool.ainvoke({"user_id": user_id})
            elif tool.name in ("query_orders", "get_order_status"):
                result = await tool.ainvoke({"user_id": user_id} if "orders" in tool.name else {})
            elif tool.name == "search_knowledge_base":
                result = await tool.ainvoke({"keyword": "常见问题"})
            elif tool.name == "create_ticket":
                result = await tool.ainvoke({"user_id": user_id, "problem": "general"})
            elif tool.name == "transfer_to_human":
                result = await tool.ainvoke({"reason": "用户请求"})
            else:
                result = "工具执行完成"
            # 工具正常结果封装成带工具名称标记的AI消息
            return AIMessage(content=f"[{tool.name}] {result}")
        # 工具调用异常捕获，返回失败日志消息
        except Exception as e:
            return AIMessage(content=f"[{tool.name} 执行失败] {e}")
    # asyncio.gather 并发并行执行所有工具，不用串行等待
    results = asyncio.gather(*[call_one(t) for t in valid_tools])
    return list(results)

# Executor 主节点入口函数，接收全局状态，更新并返回新状态
async def executor_node(state: AgentState) -> AIMessage:
    """
    执行节点：规划 → 工具调用 → 收集结果

    如果 needs_human=True，跳过执行，直接进 human 节点

    模型路由：
      - 简单意图（general）→ 小模型（省资源）
      - 复杂意图（complaint/refund）→ 大模型（高质量规划）
    """
    # 前置判断：路由节点标记需要人工介入，则直接跳过所有规划、工具流程
    if state.get("needs_human"):
        return {
            "plan": "转人工处理，跳过执行",
        }

    # 从全局状态取出识别出的用户意图，默认general通用咨询
    intent = state.get("intent", "general")
    # 取出全流程所有消息记录
    messages = state.get("messages", [])

    # 统一使用默认 LLM（智谱 GLM-4）
    llm = get_llm()

    # 如果是 general 意图，直接查询知识库并返回结果
    if intent == "general":
        user_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_msg = msg.content
                break

        from src.tools import search_knowledge_base
        try:
            keyword = user_msg
            for kw in ["退货", "换货", "发票", "配送", "优惠", "支付", "售后"]:
                if kw in keyword:
                    keyword = kw
                    break
            else:
                keyword = user_msg.replace("是什么", "").replace("怎么", "").replace("如何", "").replace("？", "").strip()[:10]

            result = await search_knowledge_base.ainvoke({"keyword": keyword})
            return {"messages": [AIMessage(content=result)]}
        except Exception as e:
            return {"messages": [AIMessage(content=f"抱歉，无法回答您的问题。")]}

    # 如果是 customer_info 意图，查询客户信息
    if intent == "customer_info":
        user_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_msg = msg.content
                break

        # 提取 user_id
        import re
        user_id_match = re.search(r'user00[123]', user_msg)
        user_id = user_id_match.group() if user_id_match else "user001"

        from src.tools import get_customer_info
        try:
            result = await get_customer_info.ainvoke({"user_id": user_id})
            return {"messages": [AIMessage(content=result)]}
        except Exception as e:
            return {"messages": [AIMessage(content=f"抱歉，无法查询客户信息。")]}

    # 如果是 order_query 意图，查询订单
    if intent == "order_query":
        user_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_msg = msg.content
                break

        import re
        user_id_match = re.search(r'user00[123]', user_msg)
        user_id = user_id_match.group() if user_id_match else "user001"

        from src.tools import query_orders
        try:
            result = await query_orders.ainvoke({"user_id": user_id})
            return {"messages": [AIMessage(content=result)]}
        except Exception as e:
            return {"messages": [AIMessage(content=f"抱歉，无法查询订单信息。")]}

    # 组装简短历史上下文：只取最后3条消息，避免超长token
    history_context = ""
    for msgs in messages[-3:]:
        # 区分角色标记用户/助手
        role = "用户" if isinstance(msgs, HumanMessage) else "助手"
        # 每条消息截断前100字符，防止文本过长
        history_context += f"{role}: {msgs.content[:100]}\n"

    # Step 1：调用内部规划函数，生成执行计划 + 要调用的工具列表
    plan, tools_needed = await _planner(llm, intent, history_context)

    # Step 2：并行执行全部规划出来的工具，拿到业务数据结果
    tool_results = await _execute_tools(tools_needed, state.get("user_id"), state.get("session_id"))

    # 整合所有工具输出，封装一条汇总消息存入全局message，供Reviewer审核
    if tool_results:
        tool_summary = "\n".join(f"- {t.content}" for t in tool_results)
        # 组装带执行计划+工具结果的AI消息
        planning_msg = AIMessage(
            content=f"[执行计划] {plan}\n\n[工具执行结果]\n{tool_summary}"
        )
    else:
        # 无需调用工具，只保留计划文本
        planning_msg = AIMessage(content=f"[执行计划] {plan}（无需调用工具）")

    # 更新全局状态：存入本次执行计划、追加工具汇总消息
    return {
        "plan": plan,
        "messages": [planning_msg],
    }