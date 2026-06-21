"""
配置模块测试
"""

def test_config_load():
    """测试配置加载"""
    from src.config import LLM_CONFIG, REDIS_CONFIG, SECURITY_CONFIG

    assert LLM_CONFIG is not None
    assert LLM_CONFIG["model"] == "qwen-med:7b"
    assert "base_url" in LLM_CONFIG

    assert REDIS_CONFIG["host"] == "127.0.0.1"
    assert REDIS_CONFIG["port"] == 6379

    assert SECURITY_CONFIG["enable_input_guard"] is True
    assert "blacklist_path" in SECURITY_CONFIG

    print("[PASS] config load test passed")


if __name__ == "__main__":
    test_config_load()
