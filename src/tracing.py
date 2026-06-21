"""
链路追踪模块
pip install opentelemetry-api opentelemetry-sdk
pip install sentry-sdk
功能：
1. OpenTelemetry 集成
2. 请求链路追踪
3. 性能指标采集
4. Sentry 错误监控

用于：
- 定位慢请求
- 分析系统瓶颈
- 监控错误率
"""
import os
import time
import uuid
# 协程本地存储，隔离每个请求的上下文数据
from contextvars import ContextVar
from functools import wraps
from typing import Optional

import sentry_sdk
from opentelemetry import trace
# 追踪器提供者，全局管理链路实例
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Span, Status, StatusCode

try:
    # 导入FastAPI、Redis自动集成插件
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    # 加载集成列表
    _SENTRY_INTEGRATIONS = [FastApiIntegration(), RedisIntegration()]
except ImportError:
    # sentry_sdk >= 2.0 版本会自动识别FastAPI/Redis，无需手动集成
    _SENTRY_INTEGRATIONS = []

# 全局单例追踪器，全局复用，避免重复创建
_tracer: Optional[trace.Tracer] = None

def init_tracing(service_name = "ecommerce_agent"):
    """初始化链路追踪"""
    global _tracer

    # 创建OTel追踪提供者
    provider = TracerProvider()
    # 开发环境使用控制台打印链路信息
    if True: # 始终用 Console，生产环境可替换为 OTLP exporter
        processor = BatchSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)

    # 设置全局追踪者
    trace.set_tracer_provider(provider)
    # 获取当前服务的追踪实例
    _tracer = trace.get_tracer(service_name)

    # 初始化Sentry异常监控（配置有效才启用）
    sentry_dsn = os.getenv("SENTRY_DSN", "")  # 替换为真实的 Sentry DSN
    if sentry_dsn and sentry_dsn != os.getenv("SENTRY_DSN", ""):
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=_SENTRY_INTEGRATIONS,
            traces_sample_rate=0.1, #  # 链路采样率：只采集10%请求，降低性能消耗
            environment=os.getenv("SENTRY_ENVIRONMENT", ""),
        )

    return _tracer

def get_tracer() -> trace.Tracer:
    """懒加载获取全局追踪器，未初始化则自动执行初始化"""
    global _tracer
    if _tracer is None:
        _tracer = init_tracing()
    return _tracer

class RequestContext:
    """请求上下文管理类
    基于ContextVar实现协程隔离存储，每个请求独立一套数据，不会串参数
    全局任意位置读取用户ID、会话ID、请求ID、请求耗时
    """
    # 协程本地变量，默认空字符串
    _request_id: ContextVar[str] = ContextVar("request_id", default="")
    _user_id: ContextVar[str] = ContextVar("user_id", default="")
    _session_id: ContextVar[str] = ContextVar("session_id", default="")
    _start_time: ContextVar[float] = ContextVar("start_time", default=0.0)

    @classmethod
    def set(cls, request_id: str = None, user_id: str = "", session_id: str = ""):
        """存入当前请求的上下文信息
        :param request_id: 请求唯一ID，不传自动生成uuid
        :param user_id: 当前操作用户ID
        :param session_id: 对话会话ID
        """
        cls._request_id.set(request_id or str(uuid.uuid4()))
        cls._user_id.set(user_id)
        cls._session_id.set(session_id)
        # 记录请求进入时间戳，用于计算总耗时
        cls._start_time.set(time.time())

    @classmethod
    def get_request_id(cls) -> str:
        return cls._request_id.get()
    @classmethod
    def get_user_id(cls) -> str:
        return cls._user_id.get()
    @classmethod
    def get_session_id(cls) -> str:
        return cls._session_id.get()
    @classmethod
    def get_elapsed_ms(cls):
        """获取从请求进入到当前的总耗时（毫秒）"""
        return (time.time() - cls._start_time.get()) * 1000


class TraceSpan:
    """追踪跨度管理器
    with 上下文管理器封装OpenTelemetry原生span，简化埋点代码
    自动绑定request_id、user_id，自动捕获异常标记链路错误状态
    """
    def __init__(self, name: str, attributes: dict = None):
        # span名称，标记当前执行的业务步骤
        self.name = name
        # 自定义标签键值对，存入链路详情
        self.attributes = attributes or {}
        # 原生OTel跨度对象，初始为空
        self.span: Optional[Span] = None

    """进入with代码块时执行：创建span、写入标签"""
    def __enter__(self):
        tracer = get_tracer()
        self.span = tracer.start_span(self.name)

        # 设置属性
        for key, value in self.attributes.items():
            if value is not None:
                self.span.set_attribute(key, str(value))

        # 设置上下文属性
        self.span.set_attribute("request_id", RequestContext.get_request_id())
        self.span.set_attribute("user_id", RequestContext.get_user_id())

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # 记录错误
            self.span.set_status(Status(StatusCode.ERROR))
            self.span.record_exception(exc_val)
        else:
            self.span.set_status(Status(StatusCode.OK))

        self.span.end()
        return False  # 不吞掉异常

    def add_event(self, name: str, attributes: dict = None):
        """添加事件"""
        if self.span:
            self.span.add_event(name, attributes or {})

def trace_span():
    """追踪装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with TraceSpan(func.__name__, {"function": func.__module__ + "." + func.__qualname__}):
                return func(*args, **kwargs)
        return wrapper
    return decorator

class PerformanceMonitor:
    """性能监控"""

    def __init__(self):
        self.spans = {}

    def start(self, name: str) -> str:
        """开始计时"""
        span_id = str(uuid.uuid4())
        self.spans[name] = {
            "id": span_id,
            "start": time.time(),
        }
        return span_id

    def end(self, name: str) -> Optional[float]:
        """结束计时，返回耗时（秒）"""
        if name not in self.spans:
            return None

        elapsed = time.time() - self.spans[name]["start"]
        self.spans[name]["elapsed"] = elapsed
        return elapsed

    def get_report(self) -> dict:
        """获取性能报告"""
        return {
            name: {
                "elapsed_ms": data.get("elapsed", 0) * 1000,
            }
            for name, data in self.spans.items()
            if "elapsed" in data
        }

# 全局实例
_perf_monitor: Optional[PerformanceMonitor] = None


def get_perf_monitor() -> PerformanceMonitor:
    global _perf_monitor
    if _perf_monitor is None:
        _perf_monitor = PerformanceMonitor()
    return _perf_monitor


def log_request_metrics(
    user_id: str,
    session_id: str,
    message: str,
    elapsed_ms: float,
    cached: bool = False,
    error: str = None
):
    """记录请求指标（可用于日志分析或 APM）"""
    metrics = {
        "type": "request",
        "request_id": RequestContext.get_request_id(),
        "user_id": user_id,
        "session_id": session_id,
        "message_length": len(message),
        "elapsed_ms": round(elapsed_ms, 2),
        "cached": cached,
    }

    if error:
        metrics["error"] = error

    # 打印到控制台（生产环境可替换为 Prometheus/InfluxDB）
    status = "ERROR" if error else "OK"
    print(f"[{status}] {metrics}")
