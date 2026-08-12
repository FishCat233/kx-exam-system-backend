# KX Exam System — Backend

C 语言在线考试系统后端服务，基于 FastAPI + SQLAlchemy + SQLite 构建。

## 技术栈

- **Web 框架**：FastAPI
- **ORM**：SQLAlchemy（异步，aiosqlite 驱动）
- **数据库**：SQLite
- **认证**：JWT（pyjwt）+ argon2 密码哈希
- **实时通信**：WebSocket（websockets）
- **数据校验**：Pydantic v2
- **数据库迁移**：Alembic
- **包管理**：uv

## 快速开始

### 环境要求

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/)

### 安装与运行

```bash
# 安装依赖
uv sync

# 启动开发服务器
uv run uvicorn app.main:app --reload

# 启动后访问：
# - API 文档：http://localhost:8000/docs
# - 数据库管理：http://localhost:8000/admin/  (由 admin.py 提供)
```

### 运行测试

```bash
uv run pytest                          # 运行全部测试
uv run pytest tests/ -v                # 详细输出
uv run pytest --cov=app --cov-report=html  # 覆盖率报告
```

### 代码质量

```bash
uv run ruff check .                    # 代码检查
uv run ruff format .                   # 代码格式化
```

### 数据库迁移

```bash
cd alembic
alembic revision --autogenerate -m "描述"   # 生成迁移
alembic upgrade head                         # 应用迁移
```

## 项目结构

```
xmn-exam-system-backend/
├── app/
│   ├── main.py              # 应用入口，FastAPI 实例
│   ├── config.py            # 配置管理（pydantic-settings）
│   ├── database.py          # 数据库连接与会话管理
│   ├── models/              # SQLAlchemy 数据模型
│   │   ├── admin.py
│   │   ├── exam.py
│   │   ├── student.py
│   │   ├── problem.py
│   │   └── operation_log.py
│   ├── schemas/             # Pydantic 请求/响应 Schema
│   ├── routers/             # API 路由
│   │   ├── auth.py          # 认证（考生登录/全屏检测/管理员登录）
│   │   ├── exams.py         # 考试 CRUD
│   │   ├── problems.py      # 题目管理
│   │   ├── code.py          # 代码保存与交卷
│   │   ├── admin.py         # 管理员账号管理
│   │   ├── logs.py          # 操作日志
│   │   ├── dashboard.py     # 仪表盘
│   │   ├── export.py        # 数据导出
│   │   └── ws.py            # WebSocket 端点
│   └── utils/               # 工具函数
├── tests/                   # pytest 测试用例
├── alembic/                 # 数据库迁移
├── scripts/                 # 构建/部署脚本
├── pyproject.toml           # 项目配置与依赖
└── Dockerfile               # Docker 构建文件
```

## API 概览

### 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/student/login` | 考生登录 |
| POST | `/api/auth/student/fullscreen` | 全屏状态上报 |
| POST | `/api/auth/admin/login` | 管理员登录 |
| POST | `/api/auth/admin/verify` | 验证管理员 Token |

### 考试与题目
| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/api/exams` | 考试列表 / 创建 |
| GET/PUT/DELETE | `/api/exams/:id` | 考试详情 / 修改 / 删除 |
| GET/POST | `/api/exams/:exam_id/problems` | 题目列表 / 添加 |
| PUT/DELETE | `/api/problems/:id` | 修改 / 删除题目 |

### 代码与交卷
| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/api/code/:problem_id` | 获取 / 保存代码 |
| POST | `/api/code/submit` | 交卷 |

### 管理功能
| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/api/admin/admins` | 管理员列表 / 创建 |
| GET/POST | `/api/admin/exams/:exam_id/students` | 考生列表 / 批量导入 |
| GET | `/api/admin/students/:student_id` | 考生详情 |
| POST | `/api/admin/students/:student_id/force-submit` | 强制收卷 |
| GET | `/api/admin/dashboard/:exam_id` | 仪表盘 |
| GET | `/api/admin/exams/:exam_id/export` | 导出考试数据（ZIP） |

### WebSocket
| 端点 | 说明 |
|------|------|
| `/ws?token=<websocket_token>` | 考生实时连接，用于防作弊监控 |

> 完整 API 文档见 [docs/backend/api.md](../docs/backend/api.md) 和 Swagger UI（`/docs`）

## 部署

### 镜像发布

release-please 打出版本 tag（`v*`）后，GitHub Actions 自动构建镜像并推送到 GHCR：

- `ghcr.io/fishcat233/kx-exam-system-backend` — 后端
- `ghcr.io/fishcat233/kx-exam-system-frontend` — 前端

每个版本同时推 `{version}` 和 `latest` 两个 tag。镜像均为 public，部署机无需登录即可拉取。

### Docker Compose 部署

`docker-compose.yml` 位于本仓库根目录，编排 backend、frontend、PostgreSQL 三个服务，全部使用 GHCR 镜像。

```bash
# 1. 创建环境变量文件（SECRET_KEY、SUPER_ADMIN_PASSWORD、WS_HOST 必填）
cp .env.example .env

# 2. 启动
docker compose up -d

# 3. 升级
docker compose pull && docker compose up -d
```

访问方式：

- 前端：`http://<部署机地址>:80`
- API 文档：`http://127.0.0.1:8000/docs`（backend 端口仅映射本机）

注意事项：

- `WS_HOST` 必须填浏览器能访问到的部署机地址（域名或 IP）。WebSocket 连接地址由后端在登录响应中下发，填错会导致考生全屏检测后无法建立监控连接。
- 前端静态资源与 API、WebSocket 走同源反代（Caddy 转发 `/api` 与 `/ws` 到 backend），浏览器只需要访问 80 端口。
- `CORS_ORIGINS` 默认 `["*"]`。同源部署下浏览器不会发起跨域请求，需要收紧时在 `.env` 中覆盖。
- 若部署机 8000 端口不可用，可临时去掉 `ports` 中 `127.0.0.1:8000:8000` 的映射。

## 文档

- [API 接口](../docs/backend/api.md)
- [数据模型](../docs/backend/models.md)
- [WebSocket 协议](../docs/backend/websocket.md)
- [业务逻辑流程](../docs/backend/flows.md)
- [后端开发规则](../docs/backend/rules.md)
- [项目架构](../docs/architecture.md)

## License

MIT
