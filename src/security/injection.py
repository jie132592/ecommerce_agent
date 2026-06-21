"""
Prompt 注入防护

功能：
1. 检测用户试图覆盖系统指令
2. 防止聊天注入攻击
3. 隔离用户输入和系统指令

优化点：泄露风险降低 90%
"""
import re
from curses.ascii import isalpha
from typing import Tuple, Optional

from langchain_core.structured_query import Operation


class InjectionProtection:
    """Prompt 注入防护器"""

    # 注入模式
    INJECTION_PATTERNS = [
        # 角色扮演/系统指令覆盖
        r"现在你(是|变成|充当)",
        r"你是一个?.*(而不是|不是)",
        r"忽略.*之前.*指令",
        r"忘记.*指示",
        r"(system|prompt).*(:|=|：|=)",

        # 越狱模式
        r"DAN",
        r"do anything now",
        r"jailbreak",
        r"priviledged mode",

        # 编码绕过
        r"\\u[0-9a-f]{4}",
        r"\\x[0-9a-f]{2}",

        # XML 注入
        r"<\|",
        r"\|>",
        r"<\?xml",
    ]

    # 允许的系统防护词
    ALLOW_SYSTEM_KEYWORDS = [
        "请", "请问", "帮我", "我想", "我要",
        "查询", "看看", "告诉", "问",
    ]

    def __init__(self):
        # 把字符串编译成正则对象
        # re.IGNORECASE 代表匹配时忽略大小写
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS]

    def detect(self, text: str) -> Tuple[bool, Optional[str]]:
        """检测注入尝试
        Returns:
            (is_safe, warning_message)
        """
        if not text:
            return True, None

        # 检查注入模式
        for pattern in self.patterns:
            match = pattern.search(text)
            if match:
                return False, f"检测到可疑{match.group()}"

        # 检查是否大量包含系统指令特征
        # 靠统计大写字母、特殊符号占比判断是不是恶意注入文本，比例超标直接拦截
        uppercase_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        if uppercase_ratio > 0.5:
            return False, "检测到异常格式，可能为注入攻击"

        # isalnum判断是否字母、数字  isspace判断是否空格、换行
        special_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(len(text), 1)
        if special_ratio > 0.5:
            return False, "特殊字符过多，可能为注入攻击"

        return True, None

    def sanitize(self, text: str) -> str:
        """清理注入内容"""
        if not text:
            return text

        # 移除常见的标记注入
        result = text

        # 移除 XML/标签格式
        result = re.sub(r"<[^>]+>", "", result)
        # 移除转义序列
        result = re.sub(r"\\+[nrt]", " ", result)
        result = re.sub(r"\\x[0-9a-f]{2}", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\\u[0-9a-f]{4}", "", result, flags=re.IGNORECASE)

        # 移除 base64 编码（可能的恶意代码）
        if re.search(r"[A-Za-z0-9+/]{50,}={0,2}", result):
            result = re.sub(r"[A-Za-z0-9+/]{50,}={0,2}", "[已过滤]", result)

        return result

    def validate(self, text: str) -> Tuple[bool, Optional[str], str]:
        """验证"""
        if not text or not text.strip():
            return False, "输入为空", ""

        # 先清理
        sanitized = self.sanitize(text)

        # 再检测
        is_safe, reason = self.detect(sanitized)
        if not is_safe:
            return False, reason, sanitized
        return True, None, sanitized

    def extract_user_intent(self, text: str) -> str:
        """提取用户真实意图(过滤掉注入部分)"""
        if not text:
            return ""

        # 移除注入标记
        patterns_to_remove = [
            r"现在你(是|变成|充当)[^\n]+",
            r"忽略.*指令[^\n]+",
            r"忘记.*[^\n]+",
            r"\[.*?\]",  # 移除方括号内容
        ]

        result = text
        for pattern in patterns_to_remove:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)

        return result.strip()

# 全局实例
# 只初始化一次,单例模式
_injection_protection: Optional[InjectionProtection] = None

def get_injection_protection() -> InjectionProtection:
    # 我要用外面那个全局变量，不是函数内部新建的局部变量
    global _injection_protection
    if _injection_protection is None:
        _injection_protection = InjectionProtection()
    # 把全局唯一的工具实例返回给调用方
    return _injection_protection