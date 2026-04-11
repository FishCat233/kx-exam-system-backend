"""FastAPI 应用入口."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.routers import admin, auth, code, exams, logs, problems, ws
from app.utils.exceptions import APIException


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理.

    Args:
        app: FastAPI 应用实例
    """
    # 启动时初始化数据库
    await init_db()
    yield
    # 关闭时清理资源


app = FastAPI(
    title=settings.app_name,
    description="C语言考试系统后端 API",
    version="0.1.0",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(exams.router)
app.include_router(problems.router)
app.include_router(code.router)
app.include_router(admin.router)
app.include_router(logs.router)
app.include_router(ws.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """健康检查端点.

    Returns:
        健康状态
    """
    return {"status": "healthy"}


@app.get("/")
async def root() -> dict[str, str]:
    """根路径.

    Returns:
        欢迎信息
    """
    return {"message": "Welcome to XMN Exam System API"}


# 异常处理 - 自定义 API 异常
@app.exception_handler(APIException)
async def api_exception_handler(request, exc: APIException):
    """处理 API 异常.

    Args:
        request: 请求对象
        exc: API 异常

    Returns:
        JSON 响应
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail},
    )


# 异常处理 - FastAPI HTTPException
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """处理 HTTP 异常.

    Args:
        request: 请求对象
        exc: HTTP 异常

    Returns:
        JSON 响应
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail},
    )
