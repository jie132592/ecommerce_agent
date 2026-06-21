from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables.graph import Graph
from langgraph.constants import START, END
from langgraph.graph import StateGraph

from agent.executor import executor_node
from agent.reviewer import reviewer_node
from agent.router import router_node
from agent.state import AgentState
from llm import get_llm
from prompts import FINAL_ANSWER


async def human_node(state: AgentState) -> AgentState:
    """人工处理节点"""
    # 意图分类
    intent = state.get('intent', 'unknown')
    # 转人工原因
    escalation_reason = state.get('escalation_reason', "需要人工处理")

    templates = {
        "complaint": "非常抱歉给您带来了不好的体验，我已经为您记录并升级处理。我们的客服专员会在24小时内联系您，请保持手机畅通。如有紧急问题，可直接拨打客服热线：400-123-4567。",
        "refund": "您的退款/退货请求我已经为您提交，将会由专人为您处理，预计1-3个工作日内完成。如有疑问可拨打热线：400-123-4567。",
        "unknown": "抱歉，我暂时无法准确理解您的问题，已为您转接人工客服，请稍候。",
    }

    response = templates.get(intent, templates["unknown"])

    return {
        "messages": [AIMessage(content=f"[人工客服] {escalation_reason}\n\n{response}")],
        "needs_human": True
    }

# 生成最终回复节点（整合所有上下文，生成自然语言回复）
async def final_answer_node(state: AgentState) -> AgentState:
    """综合所有 Agent 输出，生成最终回复"""
    llm = get_llm()

    messages = state.get("messages", [])
    # 收集所有AI节点输出内容，作为上下文供给最终总结
    context = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            context.append(msg.content)

    try:
        res = await llm.ainvoke([
            HumanMessage(content=FINAL_ANSWER.render(context="\n".join(context))),
        ])
        final_text = res.content
    except Exception as e:
        final_text = "抱歉，服务暂时繁忙，请稍后再试。"

    return {
        "messages": [AIMessage(content=final_text)]
    }

# 流程分支判断
def should_escalate(state: AgentState) -> str:
    """Router 之后：是否转人工"""
    if state.get("needs_human"):
        return "human"
    return "executor"

def should_revision(state: AgentState) -> str:
    """Review审核完成之后，判断是否需要重新执行工具"""
    # 审核节点标记需要重跑流程
    if state.get("needs_revision"):
        # 从plan字段读取重试标记，控制最多重试2次上限
        plan = state.get("plan", "")
        if "[重试2次]" in plan:
            # 最多重试2次，强制结束
            return "final"
        return "planner"
    return "final"

def build_supervisor_graph():
    graph = StateGraph(AgentState)

    # 意图分类路由节点
    graph.add_node("router", router_node)
    # 工具并行执行节点（查询订单/退款等）
    graph.add_node("executor", executor_node)
    # 结果反思审核打分节点
    graph.add_node("reviewer", reviewer_node)
    # 人工介入兜底节点
    graph.add_node("human", human_node)
    # 整合输出最终答复节点
    graph.add_node("final", final_answer_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        should_escalate,
        {
            "human": "human",
            "executor": "executor",
        }
    )
    graph.add_edge("executor", "reviewer")
    graph.add_conditional_edges(
        "reviewer",
        should_revision,
        {
            "final": "final",
            "planner": "executor",
        }
    )
    graph.add_edge("human", "final")
    graph.add_edge("final", END)

    return graph.compile()