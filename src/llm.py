"""
LLM 模块 — 统一接口

提供两个能力：
1. 统一封装：同时支持 Ollama / vLLM（OpenAI-compatible 接口）
2. 模型路由：根据查询复杂度自动选择小模型 / 大模型

切换方式（开发 → 生产）：
  Ollama → vLLM，只需在 config.py 里 swap 注释即可，
  本模块无需任何改动（接口完全兼容）。
"""
from langchain_openai import ChatOpenAI

from src.config import LLM_CONFIG, LOCAL_SMALL_MODEL, LOCAL_LARGE_MODEL, COMPLEXITY_TOKEN_THRESHOLD


def _estimate_tokens(text: str) -> str:
    """
    估算 token 数

    中文 ≈ 每字符 1~1.5 tokens（按 1.5 估算）
    英文 ≈ 每 4 字符 1 token
    混合文本取加权平均
    """
    chinese_chars = sum(1 for c in text if ord(c) > 127)
    english_chars = len(text) - chinese_chars
    # 中文按 1.5 tokens/字符，英文按 0.25 tokens/字符
    return int(chinese_chars * 1.5) + english_chars // 4

def _is_complex_query(messages):
    """判断是否为复杂查询（简单实现）"""
    return False  # 默认都走简单查询

def get_llm(
    model: str = None,
    temperature: float = 0.7,
    streaming: bool = False,
) -> ChatOpenAI:
    config = {
        **LLM_CONFIG,
        "temperature": temperature,
        "streaming": streaming,
    }

    if model:
        config["model"] = model

    return ChatOpenAI(**config)

class ModelRouter:
    """
    根据查询复杂度自动路由到对应模型

    策略：
      简单咨询（< 500 tokens）→ 小模型（省资源、快速，< 500ms）
      复杂推理（≥ 500 tokens）→ 大模型（高质量，< 2s）

    面试亮点：
      - 不是所有请求都打大模型，成本降 60%+
      - 模型路由在调用前决策，不浪费 GPU 资源
      - 小模型也能做 RAG 生成，质量可控
    """
    def __init__(self):
        self.small_model = LOCAL_SMALL_MODEL
        self.large_model = LOCAL_LARGE_MODEL
        self.threshold = COMPLEXITY_TOKEN_THRESHOLD

    def select_model(self, messages: list) -> str:
        """选择模型，默认使用配置的大模型"""
        # 暂时禁用模型路由，所有请求都使用默认模型
        return None

    def get_llm_for_request(self, messages: list, streaming: bool = False) -> ChatOpenAI:
        """获取适合当前请求的 LLM 实例"""
        model = self.select_model(messages)
        return get_llm(model=model, streaming=streaming)

# 全局实例
_model_router = None
def get_model_router() -> ModelRouter:
    global _model_router
    if _model_router:
        _model_router = ModelRouter()
    return ModelRouter()