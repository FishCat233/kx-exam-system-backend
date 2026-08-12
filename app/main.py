"""FastAPI 应用入口."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer

from app.config import settings
from app.routers import admin, auth, code, exams, logs, problems, student, ws
from app.utils.exceptions import APIException


async def init_super_admin():
    """首次启动时创建超级管理员账号（已存在则跳过）."""
    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models.admin import Admin, AdminRole
    from app.utils.auth import get_password_hash

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Admin).where(Admin.role == AdminRole.SUPER_ADMIN))
        admin = result.scalar_one_or_none()

        if admin is None:
            admin = Admin(
                username=settings.super_admin_username,
                password_hash=get_password_hash(settings.super_admin_password),
                name=settings.super_admin_name,
                is_active=True,
                role=AdminRole.SUPER_ADMIN,
            )
            session.add(admin)
            await session.commit()
            print(f"超级管理员账号已创建: {settings.super_admin_username}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理.

    Args:
        app: FastAPI 应用实例
    """
    await init_super_admin()
    yield


app = FastAPI(
    title=settings.app_name,
    description="C语言考试系统后端 API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "认证", "description": "登录和认证相关接口"},
        {"name": "考试", "description": "考试管理接口"},
        {"name": "题目", "description": "题目管理接口"},
        {"name": "代码", "description": "代码保存和提交接口"},
        {"name": "管理", "description": "管理员接口"},
        {"name": "日志", "description": "操作日志接口"},
        {"name": "WebSocket", "description": "WebSocket 实时通信"},
    ],
)

# 配置 Swagger UI 的 Bearer Token 鉴权
security_scheme = HTTPBearer(
    scheme_name="Bearer",
    description="请输入 JWT Token，格式为: Bearer {token}",
    auto_error=False,
)

app.swagger_ui_init_oauth = {
    "usePkceWithAuthorizationCodeGrant": True,
}


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT Token 认证，请在请求头中携带: Authorization: Bearer {token}",
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

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
app.include_router(student.router)
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
    return {"message": "Welcome to KX Exam System API"}


# 异常处理 — 统一响应格式 { code, message, data }
@app.exception_handler(APIException)
async def api_exception_handler(request, exc: APIException):
    """处理 API 异常."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail, "data": None},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """处理 HTTP 异常."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail, "data": None},
    )
