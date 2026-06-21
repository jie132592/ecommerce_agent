"""
摘要生成模块

当对话历史超过阈值时，自动生成摘要以节省 Token
"""
from typing import List, Optional

from click import prompt
from langchain_classic.chains import llm
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from watchfiles import awatch

from src.config import LLM_CONFIG, MEMORY_CONFIG


class SummaryMemory:
    """对话摘要生成器"""
    def __init__(self, llm: ChatOpenAI = None):
        self.llm = llm or ChatOpenAI(**LLM_CONFIG)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个对话摘要助手。请将下面的对话压缩成一段简短的摘要。
要求：
1. 保留关键信息：用户身份、需求、关键约束、已解决的问题
2. 摘要用中文，简洁明了
3. 不超过 100 字
4. 直接输出摘要，不要有前缀"""),
            ("human", """对话内容：
{conversation}""")
        ])
        self.chain = self.prompt | self.llm

    def summarize(self, messages: List[BaseMessage]) -> str:
        """同步生成摘要（兼容保留）"""
        if len(messages) < MEMORY_CONFIG["summary_trigger"]:
            return ""

        conversation = self._format_conversation(messages)
        try:
            result = self.chain.invoke({"conversation": conversation})
            return result.content if hasattr(result, "content") else str(result)
        except Exception as e:
            print(f"异步摘要生成失败: {e}")
            return ""

    async def asummarize(self, messages: List[BaseMessage]) -> str:
        """异步生成摘要（推荐在 async 上下文中使用）"""
        if len(messages) < MEMORY_CONFIG["summary_trigger"]:
            return ""

        conversation = self._format_conversation(messages)

        try:
            result = await self.chain.ainvoke({"conversation": conversation})
            return result.content if hasattr(result, 'content') else str(result)
        except Exception as e:
            print(f"异步摘要生成失败: {e}")
            return ""

    def _format_conversation(self, messages: List[BaseMessage]) -> str:
        """格式化对话内容"""
        return "\n".join([
            f"{'用户' if isinstance(m, HumanMessage) else 'AI'}:{m.content}"
            for m in messages
            # 判断变量 m 是否属于括号里任意一种类型，满足就返回 True
            if isinstance(m, (HumanMessage, AIMessage))
        ])

    def should_summarize(self, messages: List[BaseMessage]) -> bool:
        """判断是否需要摘要"""
        # 排除系统消息
        actual_messages = [m for m in messages if isinstance(m, (HumanMessage, AIMessage))]
        return len(actual_messages) >= MEMORY_CONFIG["summary_trigger"]

# 全局实例
_summary_memory: Optional[SummaryMemory] = None

def get_summary_memory() -> SummaryMemory:
    global _summary_memory
    if _summary_memory is None:
        _summary_memory = SummaryMemory()
    return _summary_memory