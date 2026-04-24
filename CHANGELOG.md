# Changelog

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
