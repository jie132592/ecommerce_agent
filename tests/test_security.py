"""
安全模块测试
"""

from src.security.input_guard import InputGuard
from src.security.output_sanitizer import OutputSanitizer


def test_phone_mask():
    """测试手机号脱敏"""
    guard = InputGuard()
    is_valid, reason, masked = guard.validate("我的手机号是13812345678")

    assert is_valid is True
    assert "138****5678" in masked
    print("[PASS] phone mask test")


def test_sql_injection_detect():
    """测试SQL注入检测"""
    guard = InputGuard()
    dangerous = "'; DROP TABLE users;--"
    is_valid, reason, masked = guard.validate(dangerous)

    assert is_valid is False
    print("[PASS] SQL injection detection test")


def test_xss_detect():
    """测试XSS检测"""
    guard = InputGuard()
    dangerous = "<script>alert('xss')</script>"
    is_valid, reason, masked = guard.validate(dangerous)

    assert is_valid is False
    print("[PASS] XSS detection test")


def test_output_sanitizer():
    """测试输出脱敏"""
    sanitizer = OutputSanitizer()
    result = sanitizer.sanitize("您的手机号是13812345678")
    assert "138****5678" in result
    print("[PASS] output sanitizer test")


if __name__ == "__main__":
    test_phone_mask()
    test_sql_injection_detect()
    test_xss_detect()
    test_output_sanitizer()
    print("\n=== All security tests passed ===")
