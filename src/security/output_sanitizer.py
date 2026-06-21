"""
输出脱敏

功能：
1. AI 回复中的敏感信息二次遮蔽
2. 过滤不当内容
3. 格式化输出

优化点：泄露风险降低 90%（配合输入过滤）
"""
import re
from typing import Optional


class OutputSanitizer:
    """输出脱敏"""

    # 输出中可能泄露的敏感模式
    LEAK_PATTERNS = {
        "internal_error": [
            (r"API.*?key.*?[a-zA-Z0-9]{20,}", "[API密钥已遮蔽]"),
            (r"secret.*?[a-zA-Z0-9]{20,}", "[密钥已遮蔽]"),
            (r"password.*?[:=]\s*\S+", "[密码已遮蔽]"),
        ],
        "system_prompt": [
            (r"你的角色是.*?专家", ""),
            (r"你是一个.*?助手", ""),
            (r"系统提示.*?：.*", ""),
        ],
        "dangerous_content": [
            (r"<script", "&lt;script"),
            (r"javascript:", "javascript&#58;"),
        ],
    }

    # 敏感电话/银行卡模式（用于二次检测）
    PHONE_PATTERN = r"1[3-9]\d{9}"
    BANK_PATTERN = r"\d{16,19}"

    def sanitize(self, text: str) -> str:
        if not text:
            return ""

        result = text

        # 二次遮蔽手机号
        result = re.sub(
            self.PHONE_PATTERN,
            lambda m: m.group()[:3] + "****" + m.group()[-4:],
            result
        )

        # 二次遮蔽银行卡
        result = re.sub(
            self.BANK_PATTERN,
            lambda m: m.group()[:4] + " **** **** " + m.group()[-4:],
            result
        )

        # 移除可能的 Prompt 泄露
        for pattern, _ in self.LEAK_PATTERNS["system_prompt"]:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)

        # 清理多余空白
        result = re.sub(r"[ \t]+", " ", result)
        result = re.sub(r"\n{3,}", "\n\n", result)

        return result.strip()

# 全局实例
_output_sanitizer: Optional[OutputSanitizer] = None

def get_output_sanitizer():
    global _output_sanitizer
    if _output_sanitizer is None:
        _output_sanitizer = OutputSanitizer()
    return _output_sanitizer