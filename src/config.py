import os
from dotenv import load_dotenv

load_dotenv()

# 路由策略：
#   简单咨询（< 500 tokens）→ 小模型（省资源、快速）
#   复杂推理（≥ 500 tokens）→ 大模型（高质量）
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LOCAL_SMALL_MODEL = os.getenv("LOCAL_SMALL_MODEL", "deepseek-r1:1.5b")   # 日常咨询
LOCAL_LARGE_MODEL = os.getenv("LOCAL_LARGE_MODEL", "qwen-med:7b")    # 复杂推理

OLLAMA_CONFIG = {
    "base_url": OLLAMA_BASE_URL,
    "temperature": 0.7,
    "streaming": True,
}

# 方案二：vLLM（生产环境，内网 GPU 服务器）
#
# 安装：在 GPU 服务器上 pip install vllm
# 启动：vllm serve qwen/qwen2.5-7b --host 0.0.0.0 --port 8000
# 接口与 Ollama 完全兼容，都是 OpenAI-compatible API
# 切换时只需把 VLLM_BASE_URL 取消注释，OLLAMA_CONFIG 注释掉即可
# VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://内网GPU服务器IP:8000/v1")
# LOCAL_SMALL_MODEL = os.getenv("LOCAL_SMALL_MODEL", "deepseek-r1:1.5b")
# LOCAL_LARGE_MODEL = os.getenv("LOCAL_LARGE_MODEL", "qwen-med:7b-instruct")
# VLLM_CONFIG = {
#     "base_url": VLLM_BASE_URL,
#     "api_key": "EMPTY",           # vLLM 本地部署通常不需要 API Key
#     "temperature": 0.7,
#     "streaming": True,
# }


# 当前激活的配置（切换生产时 swap 这一块即可）
# 开发用 Ollama：
# LLM_CONFIG = OLLAMA_CONFIG.copy()
# LLM_CONFIG["model"] = LOCAL_LARGE_MODEL

# 生产用 vLLM：
# LLM_CONFIG = VLLM_CONFIG.copy()
# LLM_CONFIG["model"] = LOCAL_LARGE_MODEL

# 智谱 GLM-4（当前激活）：
LLM_CONFIG = {
    "model": "glm-4",
    "api_key": os.getenv("ZHIPU_API_KEY"),
    "base_url": os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"),
    "temperature": 0.7,
    "streaming": True
}

# 复杂度阈值（tokens），超过用大模型
COMPLEXITY_TOKEN_THRESHOLD = int(os.getenv("COMPLEXITY_TOKEN_THRESHOLD", "50"))

# Redis
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", "6379")),
    "db": int(os.getenv("REDIS_DB", "0")), # 数据库编号
    "decode_responses": True # 自动将bytes解码成字符串，不需要手动encode
}

# 缓存配置
CACHE_CONFIG = {
    "enabled": False,  # 临时禁用以便测试
    "ttl": 300, # 5分钟缓存
    "max_tokens": 2000, # 超出此长度不缓存
}

#记忆配置
MEMORY_CONFIG = {
    "window_size": 10, # 滑动窗口大小
    "summary_trigger": 20 # 触发摘要消息数
}

# 安全配置
SECURITY_CONFIG = {
    # 开启输入风控检测(用户提问、工具入参过滤)
    "enable_input_guard": True,
    # 开启输出清洗(大模型返回内容过滤敏感词、违规内容)
    "enable_output_sanitizer": True,
    # 注入防护（防Prompt注入、SQL注入、命令注入、代码注入）
    "enable_injection_protection": True,
    # 敏感词/违规黑名单路径
    "blacklist_path": os.getenv("BLACKLIST_FILE", "data/blacklist.json"),
}

# 限流配置
RATE_LIMIT_CONFIG = {
    # 是否开启限流
    "enabled": False,  # 临时关闭以便测试
    # 每秒稳定允许10个请求（令牌桶匀速发放）
    "requests_per_second": 10,
    # 突破峰值最大容纳20个请求（令牌桶最大容量）
    "burst": 20
}

# Server配置
SERVER_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "workers": 1 # 工作进程数量，windows开发只能是1
}