# Changelog

## [0.1.4](https://github.com/FishCat233/kx-exam-system-backend/compare/v0.1.3...v0.1.4) (2026-08-12)


### 🐛 Fixes

* **docker:** .dockerignore 解除 README.md 排除，修复镜像构建失败 ([bff1950](https://github.com/FishCat233/kx-exam-system-backend/commit/bff19503f4b23d784a8136aff6caac043397e048))

## [0.1.3](https://github.com/FishCat233/kx-exam-system-backend/compare/v0.1.2...v0.1.3) (2026-08-12)


### 🤖 CI

* release-please 合并后直接构建并推送镜像 ([07db1b1](https://github.com/FishCat233/kx-exam-system-backend/commit/07db1b14a3a554b112e21d60b55e13c41510c1ff))

## [0.1.2](https://github.com/FishCat233/kx-exam-system-backend/compare/v0.1.1...v0.1.2) (2026-08-12)


### 🐛 Fixes

* **docker:** Dockerfile 补充 README.md，修复镜像构建失败 ([74e888f](https://github.com/FishCat233/kx-exam-system-backend/commit/74e888fa06fe1115f5d1cf5b143eced940b13cdc))

## [0.1.1](https://github.com/FishCat233/kx-exam-system-backend/compare/v0.1.0...v0.1.1) (2026-08-12)


### ✨ Features

* **problem:** 添加选择题类型支持 ([904dd2b](https://github.com/FishCat233/kx-exam-system-backend/commit/904dd2b2d3ccb0cdcacac247e74e8939f037cb57))
* **websocket:** 添加考试中广播新题目的功能 ([e77e7fc](https://github.com/FishCat233/kx-exam-system-backend/commit/e77e7fccf647c0580f9d597907bbe14c6d2314ab))
* 新增考生题目接口并加固管理端认证 ([be29b22](https://github.com/FishCat233/kx-exam-system-backend/commit/be29b226e515ca488d1729f7148d4bf605cccf28))
* 移除考前承诺书字段，简化考试更新限制 ([05a259e](https://github.com/FishCat233/kx-exam-system-backend/commit/05a259ebd05ea05bdf2011b5c113a164d24635c5))


### 🐛 Fixes

* **admin:** 修复创建超管账户后更改配置产生的边界问题 ([68a0b50](https://github.com/FishCat233/kx-exam-system-backend/commit/68a0b50726c1ad2324dc93b22691c3fd3ed4b3f7))
* **admin:** 参考时间的默认时区不应该依赖服务器的时区 ([166073a](https://github.com/FishCat233/kx-exam-system-backend/commit/166073a6db69b9014c1d7e1e45968927b3030148))
* **auth:** 允许登录姓名包含中英文和空格 ([b6eb303](https://github.com/FishCat233/kx-exam-system-backend/commit/b6eb3037637cf264b78312716a13c7e2b7a73b8b))
* **code:** 修复 `save_code` TOCTOU 问题 ([59c4c25](https://github.com/FishCat233/kx-exam-system-backend/commit/59c4c25925675579c801041b1143e60e44893ffb))
* **code:** 修复交卷接口的 TOCTOU 漏洞 ([00a5018](https://github.com/FishCat233/kx-exam-system-backend/commit/00a501891aa7803bc4bdb2874416a824cb03f864))
* **export:** 修复导出文件直接导入内存的问题 ([188eaf0](https://github.com/FishCat233/kx-exam-system-backend/commit/188eaf04c2cd245c0363d42dc4b5364e86468348))
* **schemas:** 允许学生姓名包含字母和空格 ([1c4b954](https://github.com/FishCat233/kx-exam-system-backend/commit/1c4b954a5498f808fb5309c1346ee958bd1da932))
* **typing:** 解决 model import 时的 type 错误 ([233f407](https://github.com/FishCat233/kx-exam-system-backend/commit/233f407a7b6b425f5a678ffbd4a86d0a5e608ef0))
* **ws:** 切屏仅记录日志不再回发 warning，避免与前端切屏警告重复 ([871fc57](https://github.com/FishCat233/kx-exam-system-backend/commit/871fc579e6bf878d511ed6104a31f9116456b15e))
* **ws:** 已接受连接后发送失败视为正常断开，避免 CRITICAL 日志误报 ([f62e091](https://github.com/FishCat233/kx-exam-system-backend/commit/f62e091ccd9095d9a824cd9d932262af6aa9de97))
* 修复 PostgreSQL 迁移引发的兼容性问题 ([724d053](https://github.com/FishCat233/kx-exam-system-backend/commit/724d053a499c9f8576ec0419defecbe0bd7f8e4e))
* 修复代码相关安全问题 ([76d8208](https://github.com/FishCat233/kx-exam-system-backend/commit/76d8208308cf4d32efd3b9fd0ece93d7a0b21bbb))
* 修正测试断言格式并调整项目版本号 ([6e964b2](https://github.com/FishCat233/kx-exam-system-backend/commit/6e964b2a71e6acca06616370ffac994c64e95e6f))
* **学生管理:** 添加批量导入学生请求模型并更新相关接口 ([41e7666](https://github.com/FishCat233/kx-exam-system-backend/commit/41e7666f6def379cf0001e33e706b732fe1d753f))
* 程序运行崩溃时进行停机资源清理 ([0c246c3](https://github.com/FishCat233/kx-exam-system-backend/commit/0c246c3ac38070de973f448dd820ecef2afb63cf))


### ♻️ Refactors

* **admin:** 重写仪表盘考试时间计算 ([4532b6d](https://github.com/FishCat233/kx-exam-system-backend/commit/4532b6d9e98487b34c22a885ad6014ec25febf47))
* **auth:** 重构旧版鉴权方式，统一用依赖注入鉴权 ([1c520dd](https://github.com/FishCat233/kx-exam-system-backend/commit/1c520dd87b4519eb705ae8b8d225e315c72fee53))
* **exams:** 清理废弃字段和冗余代码 ([1c7acc1](https://github.com/FishCat233/kx-exam-system-backend/commit/1c7acc1b726b081268632c4c204763af790ab212))
* 使用 PostgreSQL 替代 SQLite 并进行功能调整 ([f214e54](https://github.com/FishCat233/kx-exam-system-backend/commit/f214e54c562e541761e0f80dc4584f03196caeb5))


### 🤖 CI

* 更新 release-please 配置和工作流 ([958b9ee](https://github.com/FishCat233/kx-exam-system-backend/commit/958b9eed23b1f41f860e3a28ce00350e813484bf))
* 添加 Docker 相关构建脚本 ([2e5aaac](https://github.com/FishCat233/kx-exam-system-backend/commit/2e5aaac698d5776501a712a58af76cbe8575455c))
* 镜像构建工作流支持手动触发 ([9208ea3](https://github.com/FishCat233/kx-exam-system-backend/commit/9208ea36468ddd1733d843d662f3fdd86a698fbd))
* 集成 ghcr 镜像发布与 Docker Compose 部署 ([0e98eb4](https://github.com/FishCat233/kx-exam-system-backend/commit/0e98eb4c02be5fa2c2e64b66aaf749031179fb1d))


### 🧰 Chores

* **main:** release 0.1.0 ([b4e0e22](https://github.com/FishCat233/kx-exam-system-backend/commit/b4e0e22ecb26157b9af12cf5f49a2fbf9ffa073d))
* **main:** release 0.1.0 ([9f445e2](https://github.com/FishCat233/kx-exam-system-backend/commit/9f445e2db48310a2d922e74c18f6ce76e8bf049f))
* README 更新及代码调整 ([7f16795](https://github.com/FishCat233/kx-exam-system-backend/commit/7f16795703a9d004d1c3f1c25814a33af23323fc))
* 更新项目版本号至0.1.0 ([2b16423](https://github.com/FishCat233/kx-exam-system-backend/commit/2b1642399e57c5d2f493c53f6b5c32112e7088cc))

## 0.1.0 (2026-04-24)


### Features

* add Bearer Token authentication button to Swagger UI ([fbceca5](https://github.com/FishCat233/kx-exam-system-backend/commit/fbceca5be3e6a18671a7a82a1ad35accfc057e6d))
* add exam data export functionality ([f9fb01b](https://github.com/FishCat233/kx-exam-system-backend/commit/f9fb01bdce95a1c20528917c4ccf2e8f7a866377))
* **auth:** 实现基于角色的权限控制系统 ([c5068da](https://github.com/FishCat233/kx-exam-system-backend/commit/c5068da93407aec86bb732f09c7c57d290b4de5f))
* enhance routers with complete CRUD operations ([254f282](https://github.com/FishCat233/kx-exam-system-backend/commit/254f282c8c9b59c8ec57ea3786f0d431785a4feb))
* **exam:** 增加考试状态变更时自动记录实际开始/结束时间 ([c5068da](https://github.com/FishCat233/kx-exam-system-backend/commit/c5068da93407aec86bb732f09c7c57d290b4de5f))
* **export:** 完善考试导出功能，增加操作日志和统计信息 ([c5068da](https://github.com/FishCat233/kx-exam-system-backend/commit/c5068da93407aec86bb732f09c7c57d290b4de5f))
* implement WebSocket service for real-time monitoring ([93d840e](https://github.com/FishCat233/kx-exam-system-backend/commit/93d840eea286712e86d502eb338e99aaa332e0f4))
* **student:** 扩展考生详情接口，包含操作日志和代码记录 ([c5068da](https://github.com/FishCat233/kx-exam-system-backend/commit/c5068da93407aec86bb732f09c7c57d290b4de5f))
* 初始化项目结构并实现基础功能 ([a30d4d1](https://github.com/FishCat233/kx-exam-system-backend/commit/a30d4d1bb7b2e5aa3a835611bd7d491af8c54e17))
* 实现日志管理功能 ([b752dee](https://github.com/FishCat233/kx-exam-system-backend/commit/b752dee8518a5951378b3eff2782becad7eaa29c))
* 实现管理员 Token 管理功能 ([c1cbdf6](https://github.com/FishCat233/kx-exam-system-backend/commit/c1cbdf60d521527a57e0f4c7375a2f80baebdb4d))
* 实现考生管理功能 ([5567ba6](https://github.com/FishCat233/kx-exam-system-backend/commit/5567ba6cb7b6730633a0703d987d2bccb06252f8))
* 实现考试管理功能 ([d04cd3a](https://github.com/FishCat233/kx-exam-system-backend/commit/d04cd3adb5712bb44e8d89429c4dedc58cab67b4))
* 添加基础工具函数和认证依赖 ([f1288d8](https://github.com/FishCat233/kx-exam-system-backend/commit/f1288d8bcc7fef2bf12e428bcd91c7c028adc9b1))
* **考试:** 自动计算考试时长并改进时间处理 ([359c826](https://github.com/FishCat233/kx-exam-system-backend/commit/359c826d7edb558657d3d021418e2c446203f607))
* 重构管理员权限系统并增强考试管理功能 ([c5068da](https://github.com/FishCat233/kx-exam-system-backend/commit/c5068da93407aec86bb732f09c7c57d290b4de5f))
* 重构管理员认证系统，使用账号密码登录替代Token机制 ([4c6cb35](https://github.com/FishCat233/kx-exam-system-backend/commit/4c6cb35d9da31c738ada7f131669ec3ce6fcd918))


### Bug Fixes

* **models:** 将枚举类从 str+enum 改为 enum.StrEnum ([c5068da](https://github.com/FishCat233/kx-exam-system-backend/commit/c5068da93407aec86bb732f09c7c57d290b4de5f))


### Documentation

* 添加MIT许可证文件 ([035fb72](https://github.com/FishCat233/kx-exam-system-backend/commit/035fb72e6eceba785bc9c639376dff09f3fb5dd4))

## 0.1.0 (2026-04-24)


### Features

* add Bearer Token authentication button to Swagger UI ([fbceca5](https://github.com/FishCat233/kx-exam-system-backend/commit/fbceca5be3e6a18671a7a82a1ad35accfc057e6d))
* add exam data export functionality ([f9fb01b](https://github.com/FishCat233/kx-exam-system-backend/commit/f9fb01bdce95a1c20528917c4ccf2e8f7a866377))
* **auth:** 实现基于角色的权限控制系统 ([c5068da](https://github.com/FishCat233/kx-exam-system-backend/commit/c5068da93407aec86bb732f09c7c57d290b4de5f))
* enhance routers with complete CRUD operations ([254f282](https://github.com/FishCat233/kx-exam-system-backend/commit/254f282c8c9b59c8ec57ea3786f0d431785a4feb))
* **exam:** 增加考试状态变更时自动记录实际开始/结束时间 ([c5068da](https://github.com/FishCat233/kx-exam-system-backend/commit/c5068da93407aec86bb732f09c7c57d290b4de5f))
* **export:** 完善考试导出功能，增加操作日志和统计信息 ([c5068da](https://github.com/FishCat233/kx-exam-system-backend/commit/c5068da93407aec86bb732f09c7c57d290b4de5f))
* implement WebSocket service for real-time monitoring ([93d840e](https://github.com/FishCat233/kx-exam-system-backend/commit/93d840eea286712e86d502eb338e99aaa332e0f4))
* **student:** 扩展考生详情接口，包含操作日志和代码记录 ([c5068da](https://github.com/FishCat233/kx-exam-system-backend/commit/c5068da93407aec86bb732f09c7c57d290b4de5f))
* 初始化项目结构并实现基础功能 ([a30d4d1](https://github.com/FishCat233/kx-exam-system-backend/commit/a30d4d1bb7b2e5aa3a835611bd7d491af8c54e17))
* 实现日志管理功能 ([b752dee](https://github.com/FishCat233/kx-exam-system-backend/commit/b752dee8518a5951378b3eff2782becad7eaa29c))
* 实现管理员 Token 管理功能 ([c1cbdf6](https://github.com/FishCat233/kx-exam-system-backend/commit/c1cbdf60d521527a57e0f4c7375a2f80baebdb4d))
* 实现考生管理功能 ([5567ba6](https://github.com/FishCat233/kx-exam-system-backend/commit/5567ba6cb7b6730633a0703d987d2bccb06252f8))
* 实现考试管理功能 ([d04cd3a](https://github.com/FishCat233/kx-exam-system-backend/commit/d04cd3adb5712bb44e8d89429c4dedc58cab67b4))
* 添加基础工具函数和认证依赖 ([f1288d8](https://github.com/FishCat233/kx-exam-system-backend/commit/f1288d8bcc7fef2bf12e428bcd91c7c028adc9b1))
* **考试:** 自动计算考试时长并改进时间处理 ([359c826](https://github.com/FishCat233/kx-exam-system-backend/commit/359c826d7edb558657d3d021418e2c446203f607))
* 重构管理员权限系统并增强考试管理功能 ([c5068da](https://github.com/FishCat233/kx-exam-system-backend/commit/c5068da93407aec86bb732f09c7c57d290b4de5f))
* 重构管理员认证系统，使用账号密码登录替代Token机制 ([4c6cb35](https://github.com/FishCat233/kx-exam-system-backend/commit/4c6cb35d9da31c738ada7f131669ec3ce6fcd918))


### Bug Fixes

* **models:** 将枚举类从 str+enum 改为 enum.StrEnum ([c5068da](https://github.com/FishCat233/kx-exam-system-backend/commit/c5068da93407aec86bb732f09c7c57d290b4de5f))


### Documentation

* 添加MIT许可证文件 ([035fb72](https://github.com/FishCat233/kx-exam-system-backend/commit/035fb72e6eceba785bc9c639376dff09f3fb5dd4))
