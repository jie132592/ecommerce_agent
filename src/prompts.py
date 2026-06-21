"""
Prompt 配置模块

- Prompt 集中管理，支持热更新（改配置不用发版）
- 模板渲染，变量注入不字符串拼接
- Prompt 版本管理，支持 Rollback

使用方式：
    from src.prompts import render_prompt

    system_prompt = render_prompt("customer_service", user_name="张三")
    # 或
    system_prompt = CUSTOMER_SERVICE.render(user_name="张三")
"""

class PromptTemplate:
    """Prompt 模板"""
    def __init__(
        self,
        name: str,
        template: str,
        version: str = "1.0.0",
        description: str = "",
    ):
        self.name = name
        self._template = template
        self.version = version
        self.description = description

    def render(self, **kwargs) -> str:
        """填充变量生成完整提示词"""
        return self._template.format(**kwargs)

    def __str__(self):
        return self._template

    def __repr__(self):
        return f"PromptTemplate(name={self.name}, version={self.version})"

# Prompt注册表
PROMPTS = {}

def _register(name: str, template: PromptTemplate):
    PROMPTS[name] = template

def render_prompt(name: str, **kwargs) -> str:
    """统一入口，按名称获取并渲染 Prompt"""
    template = PROMPTS.get("name")
    if not template:
        raise ValueError(f"Unknown prompt: {name}")
    # 调用模板自身的render方法，把传入的所有变量填充进模板，返回完整文本
    return template.render(**kwargs)

def get_prompt_info(name: str) -> dict:
    """获取 Prompt 元信息（版本、描述）"""
    template = PROMPTS.get(name)
    if template is None:
        raise ValueError(f"Unknown prompt: {name}")
    return {
        "name": template.name,
        "version": template.version,
        "description": template.description,
    }

# System Prompt — 客服主 Prompt

CUSTOMER_SERVICE = PromptTemplate(
    name="customer_service",
    template="""你是一个专业、友好的电商智能客服助手，名叫小E。

你的职责：
1. 礼貌、友好地回答客户问题
2. 使用工具查询订单、客户信息
3. 解答常见问题（退货、发票、配送、优惠等）
4. 无法解决时创建工单或转接人工

用户信息：{user_name}
会话上下文：{session_context}

重要规则：
- 始终保持专业和礼貌
- 回答要准确，不要编造信息
- 如果不确定，建议联系人工客服
- 用中文回复
- 回答简洁有条理""",
    version="1.0.0",
    description="客服主 Prompt，用于 Agent 对话",
)
_register("customer_service", CUSTOMER_SERVICE)

# Router Prompt — 意图分类

ROUTER = PromptTemplate(
    name="router",
    template="""你是一个客服意图分类器。根据用户消息，判断意图。

分类标签：
- order_query：查订单、查物流、查商品
- refund：退货、退款、取消
- complaint：投诉、差评、维权
- general：一般咨询（优惠、活动、规则等）
- unknown：无法理解或模糊

用户消息：{user_message}

只输出分类标签，不要解释。""",
    version="1.0.0",
    description="意图分类 Prompt",
)
_register("router", ROUTER)

# Executor Planner Prompt — 执行计划
PLANNER = PromptTemplate(
    name="planner",
    template="""你是一个客服任务规划助手。

根据用户意图，制定简洁的执行计划：
1. 明确要查什么信息
2. 明确按什么顺序调用工具
3. 如果信息足够直接回答，就不需要调用工具

意图：{intent}
历史上下文：
{history_context}

回复格式（只输出计划，不要解释）：
plan: [你的执行计划，一句话描述]
tools: [需要的工具列表，用逗号分隔，可为空]""",
    version="1.0.0",
    description="执行计划 Prompt",
)
_register("planner", PLANNER)

# Reviewer Prompt — 质量审核
REVIEWER = PromptTemplate(
    name="reviewer",
    template="""你是一个客服回答质量审核员。

对以下回答从 4 个维度打分（0~1），最后给出总结：

评分维度：
1. 准确性：回答内容是否正确，有没有幻觉
2. 完整性：是否完整回应了用户的所有问题点
3. 可操作性：指引是否清晰，用户知道下一步该怎么做
4. 情感温度：语气是否友好、有同理心

回答内容：
{answer_content}

格式：
score: [0~1的小数]
reason: [评分理由，一句话]
revision: [true/false，是否需要重做]

只有当所有维度都较好（≥0.7）时才 revision=false。""",
    version="1.0.0",
    description="质量审核 Prompt",
)
_register("reviewer", REVIEWER)

# Final Answer Prompt — 最终回复
FINAL_ANSWER = PromptTemplate(
    name="final_answer",
    template="""你是一个电商客服，名叫小E。请根据以下上下文，生成一段自然、友好的最终回复：

上下文：
{context}

要求：
- 直接回复用户，不要复述上下文
- 简洁有条理
- 保持专业和友好
- 用中文回复""",
    version="1.0.0",
    description="最终回复生成 Prompt",
)
_register("final_answer", FINAL_ANSWER)