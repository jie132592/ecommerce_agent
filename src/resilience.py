"""
降级响应模块

仅保留 FallbackResponse（已在 main.py 实际使用），
其他弹性机制（超时/重试/熔断）使用标准库 + tenacity，详见 customer_agent.py。
"""


class FallbackResponse:
    """降级响应模板"""

    TEMPLATES = {
        "timeout": "抱歉，您的请求处理时间较长。请稍后再试，或联系人工客服。",
        "error": "抱歉，系统繁忙，暂时无法处理您的请求。请稍后再试。",
        "circuit_open": "当前请求量较大，请稍后再试。",
        "rate_limit": "请求过于频繁，请稍后再试。",
    }

    @classmethod
    def get(cls, reason: str) -> str:
        return cls.TEMPLATES.get(reason, cls.TEMPLATES["error"])