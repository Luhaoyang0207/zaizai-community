# Handoff

_Last updated: 2026-10-28 by Claude_

## Current goal
为 zaizai 玩家社区做一个 Discord 组队机器人（Python + discord.py，Docker 部署）。计划的 15 个任务已全部在分支 `feat/zaizai-bot` 实现，自动化测试通过；剩下人工验证、填 ID 和合并。

## What was changed
- 实现：语音房间（建/删/对账/分类满自动新开）、`!pw`/`!pp` 组队命令与卡片、实时总表（Components V2，分页、超时清理）、房间面板（锁房、组队已满、`/panel`）、管理指令（`/motto`、`/ad`、`/setting`），配置由 `config/settings.toml` 加载。
- Task 15：`Dockerfile`（python:3.12-slim，非 root）、`docker-compose.yml`（`bot-main`，可切换 dev 配置，含拆分服务注释示例）、`.env.example`、`.dockerignore`、`config/settings.dev.toml.example`、README 运行说明、`docs/TESTING.md` 增加「上线前」。
- 验证：`docker compose build` 成功；Python 3.12 容器内 `python -m pytest` 114 通过；镜像内能 import `zaizai.bot`、`zaizai.cogs.board`、`zaizai.cogs.panel`。未启动机器人（无令牌、未连 Discord）。
- 文档：新增 D-011，更新 TODO。
- 最终审查修复：总表只在内容变化时编辑（不再每次 fetch、`更新于`=内容最后变化时间）、成员进出只在有条目时刷新总表；每次 on_ready（含重连）都对账；`card.show_*` 生效、未实现的配置值启动报错；锁房同时拒绝允许连接的身份组；斜杠指令错误不再重复上报；移出分类的房间继续被记录；README 补充拆分注意事项。

## Files changed
Dockerfile, docker-compose.yml, .dockerignore, .env.example, config/settings.dev.toml.example, README.md, docs/TESTING.md, docs/HANDOFF.md, docs/TODO.md, docs/DECISIONS.md（此前任务改动见分支 git log）。

## Important decisions
见 `docs/DECISIONS.md`（D-001 ~ D-011；D-011 汇总实现期间偏离 spec/计划的裁定）。

## Problems / blockers
- `docs/TESTING.md` 的人工清单全部**未在真实 Discord 测试服务器验证**（保持未勾选）。
- `config/settings.toml` 里所有频道/服务器 ID 仍是 0，需填写（`docs/PARAMETERS.md` 第 7 节）。
- 开放项（不阻塞）：`commands.other`（其他游戏命令，当前为空 = 关闭）、广告位文字、底部文字、房间默认人数上限（当前 0 = 不限）、管理指令的权限设计（当前要求「管理服务器」）。
- 需要用户在开发者后台建正式/测试两个机器人和一个测试服务器（README 第 1 节）。

## Next recommended task
1. 建测试机器人 + 测试服务器，按 README「本地测试」启动，把 `docs/TESTING.md` 清单全部走一遍并勾选，修发现的问题。
2. 填正式服 ID，VPS 上 `docker compose up -d --build`。
3. 决定开放项，合并 `feat/zaizai-bot` 到 `main`。
