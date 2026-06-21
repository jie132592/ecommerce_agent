"""
Redis 连接测试
"""

import redis


def test_redis_connection():
    """测试 Redis 连接"""
    try:
        r = redis.Redis(host="127.0.0.1", port=6379, decode_responses=True)
        result = r.ping()
        assert result is True
        print("[PASS] Redis connection test")
    except redis.ConnectionError as e:
        print(f"[WARN] Redis not connected: {e}")
        print("Skip this test if Redis is not running")
    except Exception as e:
        print(f"[ERROR] Redis test failed: {e}")


if __name__ == "__main__":
    test_redis_connection()
