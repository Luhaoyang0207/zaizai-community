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

## D-010 — 2026-10-28 — 总表用 Components V2 布局，每条消息最多 10 个条目
布局：一个 Container = 标题 TextDisplay（模式名 · 更新于 · 页码）+ Separator + 每个条目一个 Section（TextDisplay：需求 / 发起人 · 时间 · "查看卡片"跳转链接；右侧链接按钮"{人数}人 @ {房间名}"）。
限制：Discord 官方文档（components/reference）写明 "Messages allow up to 40 total components"；discord.py 2.7.1 的 `LayoutView` 按含嵌套组件的总数校验 40，并规定文本总长上限 4000。本布局 3 + 3×条目数 ≤ 40 → 每页最多 12 条。取 10 留余量；代码把配置值夹到 12 以内，需求文字截到 150 字，保证满页 < 4000 字。
`board.show_member_count=false` 时仍保留 Section 和链接按钮，按钮只写房间名（保留进房入口，组件数不变）。
Why: 对照用户截图 2：一行一条目 + 右侧进房按钮；链接按钮不产生交互，不需要持久视图。
Rejected: 旧版 Embed + ActionRow（最多 25 个按钮，按钮不能和条目同行）；每页 12 条（贴着上限，没有余量再加组件）。

## D-011 — 2026-10-28 — 实现期间改变行为的裁定（相对 spec/计划）
- 配置里的命令不带 "!"（`commands.ranked = "pw"`），空字符串 = 该模式命令关闭。
- 尚未决定的值默认为关闭/空/0（其他游戏命令、广告文字、底部文字、人数上限）。
- 房间一空，总表条目立即移除；房间本身 30 秒后才删除。
- 锁房按钮只改 connect 权限覆盖，不动其他权限。
- 没有命令的模式不发总表。
- 总表里的需求文字做 markdown 转义，按原文单行显示。
- `/panel` 召回命令名固定，不随配置改。
- 总表"更新于"= 该页内容最后一次变化的时间；内容没变的页不再编辑（降低 API 请求，保证 99+ 房间不触发限速）。被手动删掉的总表页在下次内容变化或重启后重建。
- 锁房同时把房间里"允许连接"的身份组覆盖改为拒绝；解锁时按所在分类恢复这些身份组的 connect。
- 第一版只实现 `card.after_entry_end=keep`、`voice.reuse_empty_rooms=false`、`panel.owner_permissions=lock_only`、`panel.button_refresh/crosshair=false`；填其他值启动时报错，而不是悄悄不生效。
- 对账时，已记录但被移出受管分类的房间（频道仍在）继续记录，空了照样删除，不变成孤儿。
