"""
Review Agent — 自我反思 + 质量评分

职责：
1. 对 Executor 的输出做质量评分（0~1）
2. 判断是否需要重做（needs_revision）
3. 低于阈值时触发重试循环（最多2次）

- Self-Reflection 模式：不是直接输出，而是先评估再决定
- 质量维度：准确性、完整性、可操作性、情感温度
- 自动重试：差评自动回到 Planner，重新规划
- 与 Human-in-the-loop 联动：多次重试失败后强制人工
"""
from langchain_core.messages import AIMessage

from agent.state import AgentState
from llm import get_llm
from prompts import REVIEWER


async def reviewer_node(state: AgentState) -> AgentState:
    """审核节点：评估回答质量，决定是否重做"""
    llm = get_llm()

    # 取出当前状态里全部对话/Agent消息
    messages = state.get("messages", [])
    # 定义变量，存储Executor输出的业务回答
    last_ai_answer = ""
    # 倒序遍历消息列表，从最新消息往前找
    for msg in reversed(messages):
        # 只筛选AI产生的消息；排除以[开头的标记消息（如[人工服务]这类）
        if isinstance(msg, AIMessage) and not msg.content.startswith('['):
            # 找到最近一次Executor生成的业务内容，赋值并跳出循环
            last_ai_answer = msg.content
            break

    # 如果遍历完没找到有效业务回答
    if not last_ai_answer:
        # 直接返回审核结果：分数0，标记需要重跑流程
        return {
            "reflection_score": 0.0,
            "reflection_reason": "无有效回答",
            "needs_revision": True,
        }

    # 渲染审核提示词，把待评测的回答填充进模板
    review_prompt = [
        AIMessage(content=REVIEWER.render(answer_content=last_ai_answer))
    ]

    try:
        # 异步调用LLM，让模型对回答打分、给出修改意见
        res = await llm.ainvoke(review_prompt)
        content = res.content
        # 初始化默认值
        score = 0.5  # 默认评分0.5
        reason = ""  # 扣分/合格原因
        needs_revision = True  # 默认标记需要重做

        for line in content.split('\n'):
            # 匹配分数字段：score: 0.8
            if line.startswith("score:"):
                try:
                    # 截取冒号后面内容转浮点数
                    score = float(line[6:].strip())
                except ValueError:
                    # 转换失败用默认0.5
                    score = 0.5
            # 匹配原因字段：reason: 订单信息不全
            elif line.startswith("reason:"):
                reason = line[7:].strip()
            # 匹配是否需要重跑标记：revision: true / false
            elif line.startswith("revision:"):
                # 转小写判断是否等于true，得到布尔值
                needs_revision = line[9:].strip().lower() == "true"
        # 组装审核结果，更新全局状态
        return {
            "reflection_score": score,
            "reflection_reason": reason or content[:100],
            "needs_revision": needs_revision,
        }
    except Exception as e:
        # 返回兜底审核结果，不触发重试，直接走最终答复
        return {
            "reflection_score": 0.5,
            "reflection_reason": f"审核异常：{e}",
            "needs_revision": False,
        }

