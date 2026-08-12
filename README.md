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

发版时镜像由 release-please 自动构建推送到 GHCR。仓库根目录的 `docker-compose.yml` 编排 backend、frontend、PostgreSQL 三服务：

```bash
cp .env.example .env   # SECRET_KEY、SUPER_ADMIN_PASSWORD、WS_HOST 必填
docker compose up -d
```

`WS_HOST` 必须是考生浏览器可访问的部署机地址，登录响应中的 WebSocket 地址由此生成。

## 文档

- [术语表](../CONTEXT.md)
- [项目架构](../docs/architecture.md)
- [API 接口](../docs/backend/api.md)
- [数据模型](../docs/backend/models.md)
- [WebSocket 协议](../docs/backend/websocket.md)
- [业务逻辑流程](../docs/backend/flows.md)
- [后端开发规则](../docs/backend/rules.md)

## License

GPLv2
