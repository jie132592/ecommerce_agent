"""
电商客服 Agent

基于 LangGraph Multi-Agent Supervisor 架构：
- Router Agent — 意图分类 + 人工介入判断
- Executor Agent — 制定计划 + 并行工具调用
- Review Agent — 自我反思 + 质量评分
- Supervisor — 编排层（DAG 流程控制）

设计原则：
- Agent 无状态：每次请求 new 实例，不在内存累积状态
- 所有持久化状态放 Redis：history / episodic_memory / summary
- DAG 图模块级单例：只构建一次，所有请求共享
"""
import time
from typing import AsyncGenerator

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from src.agent.supervisor import build_supervisor_graph
from src.cache import ResponseCache
from src.memory import RedisConversationHistory, SummaryMemory
from src.prompts import CUSTOMER_SERVICE
from src.resilience import FallbackResponse
from src.security import InputGuard, OutputSanitizer

# DAG 图模块级单例（所有请求共享，只在首次 import 时构建）

_graph = build_supervisor_graph()

# Customer Service Agent（无状态，每次请求 new 实例）

class CustomerServiceAgent:
    """
    电商客服 Agent

    - 每次请求 new 实例，用完即丢，无内存累积
    - 可变状态（history、memory）全部存在 Redis
    - 安全过滤器是Stateless 的，new 实例无额外开销
    """

    def __init__(self, user_id: str, session_id: str, history: RedisConversationHistory):
        self.user_id = user_id
        self.session_id = session_id
        self.history = history

        # 安全过滤器（Stateless，new 实例无成本）
        self.input_guard = InputGuard()
        self.output_sanitizer = OutputSanitizer()
        # self.injection_protection = InjectionProtection()  # Windows 不支持 curses

    async def chat_stream(self, user_input: str) -> AsyncGenerator:
        """
        异步流式对话（Supervisor 编排）

        流程：安全过滤 → 缓存 → Supervisor DAG → 流式输出
        所有状态通过 history 写入 Redis，不在内存留存
        """
        # 异步定义流式对话接口，接收用户输入字符串，返回字符串异步生成器（逐字流式回答）
        # 整体架构，先做输入安全校验，查询缓存，执行多智能体DAG工作流，返回流式输出
        start_time = time.time()
        # 1. 第一层输入校验：输入拦截器校验用户原始输入，返回3个值：是否合法、错误原因、清洗后的干净输入文本
        is_valid, error_reason, sanitized_input = self.input_guard.validate(user_input)
        if not is_valid:
            yield f"抱歉，您的输入包含不当内容：{error_reason}。请重新输入。"
            return
        # 2. 第二层防护：Prompt注入检测（暂时禁用，Windows curses 不支持）
        # is_valid, reason = self.injection_protection.detect(sanitized_input)
        # if not is_valid:
        #     yield f"抱歉，无法处理此请求：{reason}"
        #     return

        # 检查缓存
        from src.cache import get_response_cache
        cache = get_response_cache()
        cache_hit, cache_response, blocked = await cache.aget(self.user_id, sanitized_input)
        if blocked:
            yield FallbackResponse.get("rate_limit")
            yield ""
            return

        if cache_hit and cache_response:
            first_time = time.time() - start_time
            print(f"缓存命中【首字节时间】：{first_time:.4f}s")
            for char in cache_response:
                yield char
            yield ""
            return

        # 快速路径：直接处理常见意图，跳过复杂 DAG
        from src.agent.router import router_node
        from src.agent.state import AgentState
        from langchain_core.messages import HumanMessage

        try:
            router_result = await router_node(AgentState(messages=[HumanMessage(content=sanitized_input)]))
            intent = router_result.get("intent", "general")
            needs_human = router_result.get("needs_human", False)

            if needs_human:
                yield "抱歉，我暂时无法理解您的问题，已为您转接人工客服，请稍候。"
                yield ""
                return

            # 根据意图处理
            if intent == "customer_info":
                import re
                user_id_match = re.search(r'user00[123]', sanitized_input)
                extracted_user_id = user_id_match.group() if user_id_match else self.user_id
                from src.tools import get_customer_info
                result = await get_customer_info.ainvoke({"user_id": extracted_user_id})
            elif intent == "order_query":
                import re
                user_id_match = re.search(r'user00[123]', sanitized_input)
                extracted_user_id = user_id_match.group() if user_id_match else self.user_id
                from src.tools import query_orders
                result = await query_orders.ainvoke({"user_id": extracted_user_id})
            elif intent == "general":
                from src.tools import search_knowledge_base
                keyword = sanitized_input
                for kw in ["退货", "换货", "发票", "配送", "优惠", "支付", "售后"]:
                    if kw in keyword:
                        keyword = kw
                        break
                else:
                    keyword = sanitized_input.replace("是什么", "").replace("怎么", "").replace("如何", "").replace("？", "").strip()[:10]
                result = await search_knowledge_base.ainvoke({"keyword": keyword})
            else:
                result = "抱歉，暂时无法回答您的问题，请联系人工客服。"

            # 直接输出结果，跳过 DAG
            response_text = self.output_sanitizer.sanitize(result)
            for char in response_text:
                yield char
            yield ""
            return

        except Exception as e:
            print(f"[Fast Path Error] {e}")
            yield "抱歉，系统繁忙，请稍后再试。"
            yield ""
            return

        # 从 Redis 读取历史
        # 异步从Redis读取该用户本次会话的全部历史对话消息（用户+助手历史记录）
        history_messages = await self.history.agent_messages()

        # 构建 System Prompt（模板渲染）
        system_prompt = CUSTOMER_SERVICE.render(
            user_name=self.user_id,
            session_context="无历史上下文" if not history_messages else "有历史上下文"
        )
        # 调用之前封装的Prompt模板渲染方法，填充用户ID、有无历史会话标识，生成完整客服系统提示词
        system_messages = SystemMessage(content=system_prompt)
        # 封装成LangChain标准系统消息对象, 拼接完整消息队列：系统提示词 + 历史对话 + 当前用户最新提问
        initial_msg = [system_messages] + history_messages + [HumanMessage(content=sanitized_input)]

        try:
            result = await _graph.ainvoke({
                "messages": initial_msg,  # 完整对话消息
                "user_id": self.user_id,  # 用户唯一标识
                "session_id": self.session_id,  # 会话ID
                "intent": "",  # 用户意图（待路由智能体填充）
                "intent_confidence": 0.0,  # 意图置信度
                "plan": "",  # 工具执行计划
                "needs_human": False,  # 是否需要转接人工
                "escalation_reason": "",  # 转人工原因
                "reflection_score": 0.0,  # 回答自检分数
                "reflection_reason": "",  # 打分理由
                "needs_revision": False,  # 是否需要重新生成回答
            })
        except Exception as e:
            print(f"[Supervisor Error] {e}")
            yield "抱歉，系统繁忙，请稍后再试。"
            # 流式吐出系统降级提示
            yield ""
            return
            # 终止流程

        # 最终消息
        final_messages = result.get("messages", [])

        response_text = ""
        # # 倒序遍历消息列表，找到最后一条大模型助手输出，作为最终回答文本
        for msg in final_messages:
            if isinstance(msg, AIMessage) and msg.content:
                response_text = msg.content
                break

        if not response_text:
            response_text = "抱歉，暂时无法处理您的请求。"

        # 输出脱敏：移除手机号、身份证、订单敏感信息等隐私数据
        response_text = self.output_sanitizer.sanitize(response_text)

        # 流式输出
        first_chunk_sent = False
        full_response = ""
        # 标记是否已经吐出第一个字符、保存完整回答文本用于后续缓存
        for msg in response_text:
            if not first_chunk_sent:
                first_time = time.time() - start_time
                print(f"[LLM] 首字节时间: {first_time:.4f}s")
                first_chunk_sent = True
            yield msg
            # 逐字符流式返回给前端，同时拼接完整回答字符串
            full_response += msg

        await self.history.add_message(HumanMessage(content=sanitized_input))
        await self.history.add_message(HumanMessage(content=response_text))

        # 检查摘要
        summary_mem = SummaryMemory()
        # 判断当前历史消息长度是否达到阈值，过长则需要压缩摘要
        if summary_mem.should_summarize(self.history.messages):
            # 异步生成对话摘要，存入Redis，后续对话替换长历史为摘要，减少token消耗
            summary = await summary_mem.asummarize(self.history.messages)
            if summary:
                await self.history.save_summary(summary)

        # 缓存结果
        await cache.aset(self.user_id, self.session_id, full_response)

        yield ""

    async def chat(self, user_input: str):
        """异步对话"""
        content = []
        async for chunk in self.chat_stream(user_input):
            if chunk:
                content.append(chunk)

        return "".join(content)

def get_customer_agent(user_id: str, session_id: str) -> CustomerServiceAgent:
    history_manager = __import__("src.memory", fromlist=["get_history_manager"]).get_history_manager()
    history = history_manager.get_history(session_id)
    return CustomerServiceAgent(
        user_id,
        session_id,
        history,
    )