# Decisions

Format: `D-NNN — date — decision` + why + alternatives considered.

## D-001 — 2026-10-28 — Repo-based shared memory for AI agents
Project memory lives in the repo (`AGENTS.md`, `docs/*`), not in chat history, so Codex, Claude and the owner
can pick up each other's work. `AGENTS.md` holds the rules; `CLAUDE.md` just points to it to avoid two diverging copies.

## D-002 — 2026-10-28 — 技术栈：Python + discord.py
Why: 用户选择；易读，方便后期维护和改配置。

## D-003 — 2026-10-28 — 一个进程、模块化、状态存 SQLite，按模式拆分
Why: 现在只需一个机器人，但留出拆分口子。拆分 = 新增 compose 服务 + 新令牌 + 配置里限定模式和模块；每个实例用自己的 SQLite。
Rejected: 纯内存状态（重启丢失总表）；一开始就拆成多服务（现在规模不需要）。

## D-004 — 2026-10-28 — Docker 部署，测试与线上使用不同令牌和不同服务器
Why: 用户已有 VPS + Docker；避免测试弄乱正式服务器。

## D-005 — 2026-10-28 — 临时房间空了直接删除，不复用
Why: 用户决定。建房不是瓶颈，瓶颈在发组队信息。

## D-006 — 2026-10-28 — 总表 = 每种模式一条固定消息，原地编辑
Why: 参考用户提供的现有机器人截图；比每个房间发一条新消息更不刷屏，接口调用少。

## D-007 — 2026-10-28 — 条目消失后，卡片保留不处理（card.after_entry_end=keep）
Why: 用户决定，流程简单。

## D-008 — 2026-10-28 — 发命令的频率限制交给 Discord 慢速模式，机器人不单独限制
Why: 用户决定。

## D-009 — 2026-10-28 — 管理指令的权限范围延后设计
Why: 用户决定先留着，第一版不阻塞。
