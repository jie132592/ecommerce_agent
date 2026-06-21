"""
FastAPI 主入口

功能：
1. SSE 流式对话接口
2. 会话历史查询
3. 限流保护
4. 健康检查

优化点：
- 接口响应 3s → 1s（Streaming SSE）
- 日承载 1000+（限流 + 异步）
"""
import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import redis.asyncio as redis
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from src.agent import get_customer_agent
from src.cache import get_response_cache
from src.config import SERVER_CONFIG, REDIS_CONFIG, RATE_LIMIT_CONFIG
from src.memory.redis_history import get_history_manager
from src.resilience import FallbackResponse
from src.tracing import RequestContext, TraceSpan, log_request_metrics, init_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动和关闭事件"""
    # 初始化链路追踪
    init_tracing()

    # 启动
    print("=" * 60)
    print("  电商智能客服系统启动")
    print("=" * 60)
    print(f"  服务器: http://{SERVER_CONFIG['host']}:{SERVER_CONFIG['port']}")
    print(f"  API文档: http://{SERVER_CONFIG['host']}:{SERVER_CONFIG['port']}/docs")
    print("=" * 60)

    # 测试Redis连接
    try:
        r = redis.Redis(**REDIS_CONFIG)
        r.ping()
        print(f"Redis连接成功")
    except Exception as e:
        print(f"Redis连接失败：{str(e)}")

    yield
    print("\n系统关闭中")

app = FastAPI(
    title="电商智能客服",
    version="1.0.0",
    description="基于 LangGraph 的电商客服系统，支持流式输出、智能分流、安全过滤",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 限流
limiter = Limiter(key_func=get_remote_address, default_limits=["10/second"])

# 模型数据
class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    content: str
    session_id: str
    cached: bool = False


# ===========路由=======================
@app.get("/")
# 给这个接口免除限流，不受全局 10 次 / 秒限制，随便访问。
@limiter.exempt
async def root():
    """根路径"""
    return {
        "name": "电商智能客服API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
@limiter.exempt
async def health():
    """健康检查"""
    return {"status": "healthy"}

@app.get("/stats")
@limiter.exempt
async def stats():
    """获取缓存统计"""
    cache = await get_response_cache()
    try:
        cache_stats = await cache.aget_stats()
    except Exception as e:
        cache_stats = {"error": "Redis unavailable"}

    return {
        "cache": cache_stats,
        "rate_limit": RATE_LIMIT_CONFIG
    }

@app.post("/chat")
async def chat(request: ChatRequest, ):
    """
    对话接口（流式 SSE）

    请求：
    POST /chat
    {
      "user_id": "user001",
      "message": "我的订单到哪了",
      "session_id": "sess_001"  // 可选
    }

    响应：
    SSE stream
    data: {"content": "您"}
    data: {"content": "好"}
    ...
    data: {"done": true}
    """
    request_id = str(uuid.uuid4())
    session_id = request.session_id or f"sess_{int(time.time())}"
    # 请求上下文工具
    RequestContext.set(request_id=request_id, user_id=request.user_id, session_id=session_id)

    start_time = time.time()

    # 链路追踪
    # 创建整条请求最顶层的父 span，名字chat_endpoint代表聊天接口总流程
    # 这个 with 包裹内部所有缓存、LLM、流式逻辑，整条请求的总耗时就是这个 span 的耗时
    with TraceSpan("chat_endpoint", {"user_id": request.user_id, "message_len": len(request.message)}):
        # 检查缓存（带穿透保护）
        cache = get_response_cache()
        # 是否命中缓存
        cache_hit = False
        # 缓存里存的回答文本
        cached_response = None
        # 是否被洪水限流/穿透保护拦截
        blocked = False

        # 缓存开关开启时，调用之前写的aget异步读缓存
        if cache.enabled:
            cache_hit, cached_response, blocked = await cache.aget(request.user_id, request.message)
            # 读到缓存直接打印日志，后续走缓存流式返回，不用调用大模型
            if cache_hit and cached_response:
                print(f"[缓存命中] user={request.user_id}, session={session_id}")
        # 内部异步生成器,专门用来输出 SSE 流式打字效果
        async def generate():
            nonlocal cache_hit, cached_response, blocked
            if blocked:
                error_msg = FallbackResponse.get("rate_limit")
                # 返回限流兜底话术
                yield f"data: {json.dumps({'content': error_msg}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'done': True, 'cached': False, 'blocked': True}, ensure_ascii=False)}\n\n"
                # 打印全链路指标日志
                # 记录指标
                log_request_metrics(
                    request.user_id, session_id,
                    request.message,
                    time.time() - start_time,
                    cached=False,
                    error="blocked_by_protection"
                )
                return
            # 如果命中缓存
            if cache_hit and cached_response:
                #  新开子span：cache_hit_stream，单独统计缓存流式输出耗时
                with TraceSpan("cache_hit_stream"):
                    for chunk in cached_response:
                        yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                        await asyncio.sleep(0.01) # 模拟打字机

                    total_time = time.time() - start_time
                    yield f"data: {json.dumps({'done': True, 'cached': True, 'total_time': total_time}, ensure_ascii=False)}\n\n"
                    # 记录指标
                    log_request_metrics(
                        request.user_id, session_id,
                        request.message, total_time, cached=True
                    )
                return

            # 获取 Agent
            with TraceSpan("get_agent"):
                agent = get_customer_agent(request.user_id, session_id)

            with TraceSpan("llm_stream", {"user_id": request.user_id}):
                full_response = []
                first_chunk_time = None
                try:
                    # 循环接受大模型流式分片
                    async for chunk in agent.chat_stream(request.message):
                        if not chunk:
                            continue
                        # # 记录首包耗时（首字节延迟，核心性能指标）
                        if first_chunk_time is None:
                            first_chunk_time = time.time() - start_time
                            print(f"[响应] user={request.user_id}, 首字节: {first_chunk_time:.3f}s")
                        yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                        full_response.append(chunk)

                        await asyncio.sleep(0.001)
                except Exception as e:
                    print(f"[LLM 错误] {e}")
                    error_msg = FallbackResponse.get("error")
                    yield f"data: {json.dumps({'content': error_msg}, ensure_ascii=False)}\n\n"

                total_time = time.time() - start_time
                print(f"[完成] user={request.user_id}, 总耗时: {total_time:.3f}s")
                yield f"data: {json.dumps({'done': True, 'cached': True, 'total_time': total_time})}\n\n"

                # 记录指标
                log_request_metrics(
                    request.user_id, session_id,
                    request.message, total_time, cached=False
                )
        # 返回 SSE 流式响应
        return StreamingResponse(
            generate(),
            # 响应数据类型，固定 SSE 协议标准 MIME 类型
            media_type="text/event-stream; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "connect": "keep-alive",
                "X-Session-ID": session_id,
                "X-Request-ID": request_id,
            }
        )

@app.get("/history/{user_id}/{session_id}")
async def get_history(user_id: str, session_id: str):
    """获取用户列表"""
    manager = get_history_manager()
    history = manager.get_history(user_id)
    messages = []
    for msg in await history.agent_messages():
        msg_dict = {
            "type": msg.type,
            "content": msg.content,
        }
        messages.append(msg_dict)

    return {
        "messages": messages,
        "user_id": user_id,
        "session_id": session_id,
    }

@app.delete("/history/{user_id}")
async def delete_history(user_id: str):
    """清空用户所有会话"""
    manager = get_history_manager()
    count = await manager.aclear_user_sessions(user_id)
    return {
        "status": 200,
        "msg": "success",
        "count": count,
    }

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler():
    """限流异常处理"""
    return {
        "status": 429,
        "error": "请求过于频繁，请稍后再试",
        "detail": "已触发限流保护，当前支持每分钟 60 次请求",
    }

if __name__ == '__main__':
    uvicorn.run("src.main:app",
        host=SERVER_CONFIG["host"],
        port=SERVER_CONFIG["port"],
        reload=False,
        workers=1,  # 生产环境用 gunicorn
 )