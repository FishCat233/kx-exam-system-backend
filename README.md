# KX Exam System — Backend

C 语言在线考试系统的后端服务，FastAPI + PostgreSQL，为考生端和仪表盘提供 API 与实时监控。

## 特性

- **全屏预检**：考生登录成功后强制进入浏览器全屏，失败即终止考试
- **隐形监控**：WebSocket 长连接静默上报切屏与退出全屏行为，考生无感知
- **强制收卷**：管理员远程终止考试，代码自动保存
- **操作日志**：关键行为留痕，按 normal / warning / critical 分级
- **软删除**：考试、题目、考生逻辑删除，数据不物理移除
- **数据导出**：考试数据（代码、日志、成绩）一键导出

## 快速开始

环境要求：Python >= 3.12、[uv](https://docs.astral.sh/uv/)。

```bash
uv sync                                   # 安装依赖
uv run uvicorn app.main:app --reload      # 启动开发服务器
```

启动后访问 http://localhost:8000/docs 查看 Swagger 文档。

```bash
uv run pytest        # 运行测试
uv run ruff check .  # 代码检查
```

## 部署

一套完整部署包含 backend、frontend、PostgreSQL 三个容器，编排在仓库根目录的 `docker-compose.yml`，全部使用 GHCR 镜像。发版时 release-please 自动构建镜像，服务器上无需本地编译。

### 1. 安装 Docker

```bash
curl -fsSL https://get.docker.com | sh
```

要求 Docker 24+（自带 Compose v2 插件）。安装后确认：

```bash
docker --version && docker compose version
```

### 2. 拉取部署文件

```bash
git clone --depth 1 https://github.com/FishCat233/kx-exam-system-backend.git
cd kx-exam-system-backend
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

必填三项：`SECRET_KEY`（JWT 签名密钥）、`SUPER_ADMIN_PASSWORD`（初始超级管理员密码）、`WS_HOST`（考生浏览器可访问的部署机域名或 IP，登录响应中的 WebSocket 地址由此生成）。

### 4. 启动

```bash
docker compose pull      # 拉取 GHCR 最新镜像
docker compose up -d
```

后端容器启动时自动执行数据库迁移（首次部署建表、升级时更新结构），无需手动操作。手动兜底命令：

```bash
docker compose exec backend uv run alembic upgrade head
```

### 5. 验证

```bash
curl -s http://127.0.0.1:8000/health                              # 后端健康检查
curl -s -o /dev/null -w "%{http_code}\n" http://<部署机地址>/      # 前端页面，应返回 200
```

后端端口只映射到本机，对外只开放 80 端口，API 与 WebSocket 由前端 Caddy 反代。

### 升级

```bash
docker compose pull && docker compose up -d
```

考试数据在 `pgdata` volume 中，重建容器不丢数据。

## 文档

- [术语表](../CONTEXT.md)
- [项目架构](../docs/architecture.md)
- [API 接口](../docs/backend/api.md)
- [数据模型](../docs/backend/models.md)
- [WebSocket 协议](../docs/backend/websocket.md)
- [业务逻辑流程](../docs/backend/flows.md)
- [后端开发规则](../docs/backend/rules.md)

## License

本项目采用 AGPLv3。可以自由使用、修改和分发，但衍生作品必须以 AGPLv3 开源；如果把修改后的版本作为网络服务对外提供，必须向使用者开放修改后的源码。完整条款见 [LICENSE](./LICENSE)。
