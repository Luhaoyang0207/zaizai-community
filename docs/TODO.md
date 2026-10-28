# TODO

- [x] Write down the feature list / scope（spec 与 `docs/PARAMETERS.md` 已覆盖）
- [x] Choose bot language + library + hosting（D-002、D-004）
- [x] Write architecture（`docs/superpowers/specs/2026-10-28-zaizai-bot-design.md`）
- [x] Scaffold minimal bot，带 `.env.example`

## 来自 2026-10-28 brainstorming
- [ ] 补全 `docs/PARAMETERS.md` 里标"待确认"的项（其他游戏命令、广告位内容、底部文字、房间人数上限）
- [x] 写 spec：`docs/superpowers/specs/2026-10-28-zaizai-bot-design.md`
- [x] 确认技术栈：Python + discord.py，Docker（D-002、D-004）
- [ ] 设计管理指令的权限范围（管理员 / 指定角色）

## 实现（分支 feat/zaizai-bot）
- [x] 计划 15 个任务全部实现，自动化测试通过（含 Python 3.12 容器内）
- [x] Docker、compose、README 运行说明
- [ ] 在测试服务器把 `docs/TESTING.md` 人工清单全部走一遍并勾选
- [ ] 填 `config/settings.toml`（正式）和 `config/settings.dev.toml`（测试）的频道 ID
- [ ] 合并 `feat/zaizai-bot` 到 `main`
