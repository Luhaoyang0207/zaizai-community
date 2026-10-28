# zaizai 组队机器人 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 做一个 Discord 组队机器人：加入即创建的临时语音房间、`!pw`/`!pp` 组队卡片、信息组队总表、房间面板（开/锁、组队已满）。

**Architecture:** 一个进程，功能拆成互相独立的 cog（`voice_rooms`、`lfg`、`board`、`panel`、`admin`）。所有可测试的判断逻辑写成不依赖 Discord 的纯函数；cog 只做 Discord 连接。状态存本地 SQLite；cog 之间通过 `bot.dispatch("board_dirty", mode)` 事件通知总表刷新。拆分 = 另起实例，用 `modules.enabled` / `modules.mode_scope` 限定职责。

**Tech Stack:** Python 3.12、discord.py（固定一个支持 Components V2 的版本）、标准库 `sqlite3` / `tomllib`、pytest + pytest-asyncio（仅开发）。

**Spec:** `docs/superpowers/specs/2026-10-28-zaizai-bot-design.md`；数值以 `docs/PARAMETERS.md` 为准。

## Global Constraints

- 不新增依赖：运行时只有 discord.py；开发时只有 pytest、pytest-asyncio。
- 令牌只放 `.env`（`DISCORD_TOKEN`），不得进入仓库、日志或测试。
- 每个实例用自己的 SQLite 文件，路径由环境变量 `ZAIZAI_DB_PATH` 指定。
- 命令：排位 `!pw`，匹配 `!pp`，"其他游戏"命令为空表示关闭；全角 `！` 同样识别（`commands.accept_fullwidth=true`）。
- 房间空了等 `voice.empty_delete_delay_sec`（30）秒后**直接删除**，不复用（`voice.reuse_empty_rooms=false`）。
- 每个分类最多 `voice.category_max_channels`（45）个房间，超出自动新开分类。
- 总表：每种模式一条（或多条分页）固定消息，原地编辑；刷新最多每 `board.refresh_debounce_sec`（5）秒一次；条目 `board.entry_timeout_min`（30）分钟没更新即清掉。
- 条目消失后卡片保留（`card.after_entry_end=keep`）。
- 房主只有两个按钮：开/锁、组队已满，且只有房主能点。
- 发命令频率交给 Discord 慢速模式，机器人不限制。
- 管理指令权限第一版暂用 Discord 的"管理服务器"权限（临时做法，正式方案延后设计）。
- 所有自动测试不得联网、不得连 Discord。
- 提交信息用 `feat:` / `test:` / `chore:` 前缀，每个任务结束提交一次。

## Review Focus

1. 命令的各种打法：`！pw 铂钻 3=2`、`! pw`（感叹号后有空格，用户截图里就是这样）、`!PW`、命令后没有文字、`!pwn`（不应匹配）。→ Task 2
2. 同一房间的房主重复发命令：只更新原条目，不出现第二条。→ Task 3
3. 机器人重启：记事本里已不存在的房间和条目被清掉；仍有人的未登记房间被认领；空的未登记房间被删；面板按钮重启后仍可点。→ Task 6、Task 13
4. 总表消息、卡片、面板被人手动删了：下次刷新重新发总表，不崩溃。→ Task 8、Task 12
5. 99+ 个房间：多个分类都满了要新开分类；条目多于一条消息能放的数量要分页。→ Task 4、Task 5

---

## 文件结构

```
requirements.txt  requirements-dev.txt  pyproject.toml  Dockerfile  docker-compose.yml  .env.example
config/settings.toml
src/zaizai/{models,config,commands,store,entries,placement,reconcile,asyncutil,board_sync,card,settings_view,bot}.py
src/zaizai/cogs/{voice_rooms,lfg,board,panel,admin}.py
tests/test_*.py        docs/TESTING.md
```

### Task 1: 脚手架、模型、配置加载

**Files:** Create `requirements*.txt`、`pyproject.toml`（pytest 配置：`pythonpath=src`、`asyncio_mode=auto`）、`config/settings.toml`、`src/zaizai/models.py`、`src/zaizai/config.py`、`tests/test_config.py`；Modify `docs/PARAMETERS.md`（新增"频道 ID"一节）、`.gitignore`（加 `data/`、`.env.dev`）。

**Interfaces — Produces:**
- `models.py`：`class Mode(str, Enum)`（`RANKED="ranked"`、`MATCH="match"`、`OTHER="other"`）；`@dataclass(frozen=True) Room(id:int, mode:Mode, owner_id:int, category_id:int, created_at:float, locked:bool, panel_message_id:int|None)`；`@dataclass(frozen=True) Entry(id:int, room_id:int, mode:Mode, text:str, host_id:int, card_channel_id:int, card_message_id:int, created_at:float, updated_at:float)`。
- `config.py`：`@dataclass(frozen=True) Config`，**每个 PARAMETERS.md 键一个属性（点换成下划线，如 `board_entry_timeout_min`）**，另有 `guild_id:int`、`board_channel_id:int`、`modes: dict[Mode, ModeConfig]`；`ModeConfig(mode, command:str|None, entrance_channel_id, lfg_channel_id, category_id, name_template:str)`；`load_config(path: str|Path) -> Config`；`mode_in_scope(cfg: Config, mode: Mode) -> bool`。

- [ ] **Step 1: 写失败测试** `tests/test_config.py`：`test_every_parameters_key_exists_in_settings_toml`（用正则从 `docs/PARAMETERS.md` 表格里取所有反引号键名，断言 `settings.toml` 中按点路径都能找到）；`test_load_config_values`（断言 `cfg.board_entry_timeout_min == 30`、`cfg.board_refresh_debounce_sec == 5`、`cfg.voice_category_max_channels == 45`、`cfg.voice_reuse_empty_rooms is False`、`cfg.card_after_entry_end == "keep"`、`cfg.modes[Mode.RANKED].command == "pw"`、`cfg.modes[Mode.OTHER].command is None`）。
- [ ] **Step 2: 运行确认失败** `pytest tests/test_config.py -v`，预期 FAIL（模块不存在）。
- [ ] **Step 3: 实现** 上述 `models.py`、`config.py`、`settings.toml`（值取自 PARAMETERS.md；`voice.name_template` 写成 `[voice.name_template]` 表，三种模式各一个；频道 ID 先填 0 并注明"部署时填写"）；PARAMETERS.md 新增"频道 ID"一节说明 `[guild]`、`[modes.*]` 的 ID 字段。
- [ ] **Step 4: 运行确认通过** `pytest -v`，预期全部 PASS。
- [ ] **Step 5: 提交** `chore: scaffold project, models and config loader`

### Task 2: 命令解析与组队请求判断

**Files:** Create `src/zaizai/commands.py`、`tests/test_commands.py`

**Interfaces — Produces:**
- `@dataclass(frozen=True) ParsedCommand(mode: Mode, text: str)`
- `parse_lfg_command(text: str, commands: Mapping[str, Mode], accept_fullwidth: bool = True) -> ParsedCommand | None`（`commands` 形如 `{"pw": Mode.RANKED, "pp": Mode.MATCH}`）
- `class LfgDecision(Enum)`：`IGNORE`、`NEED_VOICE`、`OK`
- `decide_lfg(parsed: ParsedCommand | None, channel_mode: Mode | None, author_room_mode: Mode | None) -> LfgDecision`（`channel_mode` 是消息所在频道对应的模式，在房间自带聊天里则为该房间的模式；`author_room_mode` 是发送者当前所在临时房间的模式，不在临时房间则为 `None`）

- [ ] **Step 1: 写失败测试**（均为 `parse_lfg_command`，`commands={"pw":RANKED,"pp":MATCH}`）：`!pw 铂钻 3=2` → `ParsedCommand(RANKED,"铂钻 3=2")`；`！pw 铂钻 3=2`（全角）同；`！ pw 铂钻 3=2` 与 `! pw x`（感叹号后有空格）→ 匹配；`!PW x` → RANKED；`!pw` → `ParsedCommand(RANKED,"")`；`!pwn x` → `None`；`hello !pw x` → `None`；`  !pp x`（前导空白）→ MATCH；多行文字保留换行；`accept_fullwidth=False` 时 `！pw x` → `None`。`decide_lfg`：`parsed=None`→IGNORE；命令模式≠`channel_mode`→IGNORE；`author_room_mode is None`→NEED_VOICE；`author_room_mode`≠命令模式→NEED_VOICE；其余→OK。
- [ ] **Step 2: 运行确认失败** `pytest tests/test_commands.py -v`
- [ ] **Step 3: 实现** 上述两个函数；用一个按 `commands` 键生成的正则（`^\s*[!！]\s*(pw|pp)(?=\s|$)\s*(.*)$`，忽略大小写，`re.DOTALL`）。
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** `feat: LFG command parsing and request decision`

### Task 3: SQLite 记事本

**Files:** Create `src/zaizai/store.py`、`tests/test_store.py`

**Interfaces — Consumes:** Task 1 的 `Room`、`Entry`、`Mode`。**Produces:** `class Store(path: str)`，方法：
- `init() -> None`（建表，开 WAL）
- 房间：`add_room(room: Room) -> None`、`get_room(room_id: int) -> Room | None`、`list_rooms(mode: Mode | None = None) -> list[Room]`、`set_locked(room_id: int, locked: bool) -> None`、`set_panel_message(room_id: int, message_id: int) -> None`、`delete_room(room_id: int) -> None`（同时删除该房间的条目）
- 条目：`upsert_entry(room_id: int, mode: Mode, text: str, host_id: int, card_channel_id: int, card_message_id: int, now: float) -> Entry`（**每个房间最多一条**）、`get_entry_by_room(room_id: int) -> Entry | None`、`delete_entry_by_room(room_id: int) -> bool`、`list_entries(mode: Mode) -> list[Entry]`
- 总表：`get_board_message_ids(mode: Mode) -> list[int]`、`set_board_message_ids(mode: Mode, ids: list[int]) -> None`
- 分类：`list_categories(mode: Mode) -> list[int]`、`add_category(mode: Mode, category_id: int) -> None`
- 设置：`get_setting(key: str, default: str | None = None) -> str | None`、`set_setting(key: str, value: str) -> None`

- [ ] **Step 1: 写失败测试**（`tmp_path` 数据库）：`test_upsert_entry_twice_keeps_one_row`（同一 `room_id` 调两次，`list_entries` 长度为 1，文字为第二次的，`created_at` 保持第一次、`updated_at` 为第二次）；`test_delete_room_removes_entry`；`test_list_entries_filters_by_mode`；`test_board_message_ids_roundtrip`；`test_state_survives_reopen`（关闭后用同一路径新建 `Store`，数据仍在）；`test_settings_default_and_override`；`test_categories_keep_insertion_order`。
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现** `Store`；每次操作开短连接或单连接加锁均可，保证重启后数据在；时间戳用传入的 `now`，不在内部取时间。
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** `feat: SQLite store for rooms, entries, boards and settings`

### Task 4: 条目生命周期与分页

**Files:** Create `src/zaizai/entries.py`、`tests/test_entries.py`

**Interfaces — Produces:**
- `find_expired(entries: Iterable[Entry], now: float, timeout_min: int) -> list[Entry]`（`now - updated_at > timeout_min*60` 才算过期，恰好等于不算）
- `sort_for_board(entries: Iterable[Entry]) -> list[Entry]`（`updated_at` 新的在前；相同时 `id` 大的在前）
- `paginate_entries(entries: Sequence[Entry], per_page: int) -> list[list[Entry]]`（**至少返回一页**；空列表返回 `[[]]`）

- [ ] **Step 1: 写失败测试**：`test_expired_boundary`（正好 30 分钟不过期，30 分 1 秒过期）；`test_sort_newest_first_tiebreak_by_id`；`test_paginate_empty_returns_one_empty_page`；`test_paginate_25_entries_per_page_10`（页长 10、10、5）；`test_paginate_exact_multiple`（20 条、每页 10 → 2 页，无空尾页）。
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现** 三个纯函数。
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** `feat: entry expiry, ordering and pagination`

### Task 5: 房间分类安置与命名

**Files:** Create `src/zaizai/placement.py`、`tests/test_placement.py`

**Interfaces — Produces:**
- `pick_category(counts: Sequence[int], max_per_category: int) -> int | None`（返回第一个未满分类的下标；全满或没有分类返回 `None`，表示要新开分类）
- `next_room_name(template: str, existing_names: Iterable[str]) -> str`（`template` 如 `"排位房 {n}"`，取最小的未被占用的 `n`，从 1 起）

- [ ] **Step 1: 写失败测试**：`test_pick_first_non_full`（`[45,10]`, 45 → 1）；`test_pick_none_when_all_full`（`[45,45,45]` → `None`）；`test_pick_none_when_no_categories`；`test_next_name_fills_gap`（已有 `排位房 1`、`排位房 3` → `排位房 2`）；`test_next_name_ignores_other_templates`（`匹配房 1` 不占用排位的 1）；`test_next_name_beyond_99`（已有 1..99 → `排位房 100`）。
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** `feat: room category placement and naming`

### Task 6: 重启对账

**Files:** Create `src/zaizai/reconcile.py`、`tests/test_reconcile.py`

**Interfaces — Produces:** `@dataclass(frozen=True) ReconcileResult(stale: frozenset[int], adopt: frozenset[int], remove: frozenset[int])`；`reconcile(db_room_ids: Collection[int], live_rooms: Mapping[int, int]) -> ReconcileResult`（`live_rooms` 是服务器里受管分类下的语音频道 ID → 当前人数）。`stale` = 记事本有、服务器没有（应删记录和条目）；`adopt` = 服务器有、记事本没有、人数>0（认领）；`remove` = 服务器有、记事本没有、人数为 0（应删频道）。

- [ ] **Step 1: 写失败测试**：`test_stale_room_detected`；`test_untracked_nonempty_is_adopted`；`test_untracked_empty_is_removed`；`test_tracked_and_live_untouched`；`test_all_empty_inputs`。
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** `feat: restart reconciliation logic`

### Task 7: 异步工具（排队、合并刷新）

**Files:** Create `src/zaizai/asyncutil.py`、`tests/test_asyncutil.py`

**Interfaces — Produces:**
- `class SerialQueue(interval_ms: int)`：`async run(self, factory: Callable[[], Awaitable[T]]) -> T`，任务严格按提交顺序执行，两次开始之间至少间隔 `interval_ms`。
- `class Debouncer(delay_sec: float, action: Callable[[Hashable], Awaitable[None]])`：`trigger(key: Hashable) -> None`。同一 `key` 在 `delay_sec` 内多次触发只执行一次 `action(key)`，且在窗口结束时执行；窗口过后再触发会再执行；不同 `key` 互不影响；`action` 抛异常不会终止后续触发。

- [ ] **Step 1: 写失败测试**（用很小的时间值，如 0.05 秒）：`test_serial_queue_keeps_order_and_spacing`；`test_debouncer_coalesces_burst`（10 次触发 → `action` 调用 1 次）；`test_debouncer_fires_again_after_window`；`test_debouncer_keys_independent`；`test_debouncer_survives_action_error`。
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** `feat: serial queue and debouncer utilities`

### Task 8: 总表同步算法

**Files:** Create `src/zaizai/board_sync.py`、`tests/test_board_sync.py`

**Interfaces — Consumes:** Task 3 `Store`、Task 4 `paginate_entries`。**Produces:**
- `class BoardGateway(Protocol)`：`async exists(message_id: int) -> bool`；`async send(mode: Mode, page: list[Entry], page_index: int) -> int`（返回新消息 ID）；`async edit(message_id: int, mode: Mode, page: list[Entry], page_index: int) -> None`；`async delete(message_id: int) -> None`
- `async sync_board(store: Store, gateway: BoardGateway, mode: Mode, pages: list[list[Entry]]) -> None`：第 i 页对应记事本里第 i 个消息 ID；ID 不存在（被手动删了）就重新 `send` 并更新记事本；页数变多就补发；页数变少就删多余消息；最终把 ID 列表写回 `store.set_board_message_ids`。

- [ ] **Step 1: 写失败测试**（用记录调用的假 `BoardGateway`）：`test_first_sync_sends_one_message_even_when_empty`；`test_existing_message_is_edited_not_resent`；`test_manually_deleted_message_is_recreated_and_id_stored`（`exists` 返回 False → 调 `send`，记事本里是新 ID）；`test_grows_to_more_pages`；`test_shrinks_deletes_extra_messages`；`test_delete_error_on_missing_message_is_ignored`。
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现** `sync_board`
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** `feat: board synchronisation with recreate and paging`

### Task 9: 机器人骨架与模块选择

**Files:** Create `src/zaizai/bot.py`、`src/zaizai/__main__.py`、`tests/test_bot_modules.py`

**Interfaces — Consumes:** Task 1 `Config`、`mode_in_scope`。**Produces:**
- `enabled_cogs(cfg: Config) -> list[str]`（返回 `cfg.modules_enabled` 中有效的 cog 模块名，如 `["voice_rooms","lfg","board","panel","admin"]`；未知名称抛 `ValueError`）
- `class ZaizaiBot(commands.Bot)`：构造时需要 `Config`、`Store`；开启 Message Content Intent；`setup_hook` 里按 `enabled_cogs` 加载 `zaizai.cogs.<name>`；暴露 `bot.cfg`、`bot.store`。
- `__main__.py`：读 `DISCORD_TOKEN`、`ZAIZAI_CONFIG`、`ZAIZAI_DB_PATH`，初始化后运行。

- [ ] **Step 1: 写失败测试**：`test_enabled_cogs_respects_config`；`test_unknown_cog_name_raises`；`test_mode_scope_limits_modes`（`mode_scope=["match"]` 时 `mode_in_scope(cfg, RANKED)` 为 False）。
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现** `enabled_cogs`、`ZaizaiBot`、`__main__`；各 cog 文件先建只含 `async def setup(bot)` 的空壳，后续任务填充。
  另加统一的错误处理（spec 第 8 节）：全局 `on_error` / 应用指令错误处理里，缺权限（`discord.Forbidden`）时在日志写明缺什么并在 `board_channel_id` 提示一次（同类错误不重复提示）；其他 Discord 临时错误（`discord.HTTPException`）重试 3 次后跳过本次，进程不退出。
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** `feat: bot skeleton with config-driven cog loading`

### Task 10: 临时语音房间 cog

**Files:** Modify `src/zaizai/cogs/voice_rooms.py`；Modify `docs/TESTING.md`（建）

**Interfaces — Consumes:** `pick_category`、`next_room_name`、`reconcile`、`SerialQueue`、`Store`、`mode_in_scope`。**Produces:** 事件 `bot.dispatch("room_created", room: Room)`；每次房间人数变化或房间被删时 `bot.dispatch("board_dirty", mode)`。

- [ ] **Step 1: 写手动测试清单** 到 `docs/TESTING.md`"语音房间"一节：进入入口房间 → 建房并被移入、发面板；分类满 45 → 自动新开分类；房间空 30 秒后被删；30 秒内重新进入不删；重启机器人后对账（建一个空的未登记房间应被删，有人的应被认领）。
- [ ] **Step 2: 实现入口监听** `on_voice_state_update`：仅处理 `mode_in_scope` 的模式；玩家进入某模式入口频道 → 经 `SerialQueue` 建房（`pick_category` 为 `None` 时新建分类并 `store.add_category`）、移动玩家、`store.add_room`、派发 `room_created`。
- [ ] **Step 3: 实现空房间删除** 房间空了启动 `voice_empty_delete_delay_sec` 秒计时，计时内有人进入则取消；到时仍空 → 删频道、`store.delete_room`、派发 `board_dirty`。人数变化时派发 `board_dirty`。
- [ ] **Step 4: 实现启动对账** `on_ready` 里收集受管分类下的语音频道与人数，调 `reconcile`：`stale` 删记录，`adopt` 补登记（房主取当前第一个在房间里的成员），`remove` 删频道；最后派发所有模式的 `board_dirty`。
- [ ] **Step 5: 在测试服务器按清单手动验证**，通过后勾选 `docs/TESTING.md` 对应项。
- [ ] **Step 6: 提交** `feat: join-to-create temporary voice rooms`

### Task 11: 组队命令 cog 与卡片

**Files:** Create `src/zaizai/card.py`、`tests/test_card.py`；Modify `src/zaizai/cogs/lfg.py`

**Interfaces — Consumes:** `parse_lfg_command`、`decide_lfg`、`Store.upsert_entry`、Task 14 的 `effective_setting`（先用 `cfg` 默认值，Task 14 接入）。**Produces:**
- `build_card(text: str, host_id: int, board_channel_id: int, now: float, ad_text: str | None, footer_text: str | None) -> discord.Embed`：标题为需求（空文字时用"组队中"）；包含到 `board_channel_id` 的频道提及（`<#id>`）和"找人组队看这里"；发起人 `<@host_id>` 与 `<t:{int(now)}:R>`；`ad_text` 不为空时显示广告位；`footer_text` 不为空时作为页脚。

- [ ] **Step 1: 写失败测试** `tests/test_card.py`：`test_card_has_requirement_host_and_board_link`（断言标题含 `铂钻 3=2`、描述含 `<@42>` 与 `<#99>`）；`test_card_without_ad_omits_ad_slot`；`test_card_footer_text`；`test_card_empty_text_uses_default_title`。
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现 `build_card`**
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 实现 cog `on_message`**：忽略机器人消息；用频道 → 模式（对应 `modes[*].lfg_channel_id`，或房间自带聊天 → 该房间的模式，受 `commands_allow_in_room_chat` 控制）调用 `decide_lfg`；`NEED_VOICE` 时回复 `commands_need_voice_msg`；`OK` 时在原消息下回复卡片、`store.upsert_entry`、派发 `board_dirty`；删除原消息开关为真则删除原消息（先发卡片再删）。
- [ ] **Step 6: 手动验证** 在 `docs/TESTING.md` 增"组队命令"一节并在测试服务器验证：三种打法（`!pw x`、`！pw x`、`! pw x`）、不在语音时的提示、在房间聊天里发、重复发命令只更新一条、删除原消息开关。
- [ ] **Step 7: 提交** `feat: LFG command handling and card`

### Task 12: 总表 cog

**Files:** Modify `src/zaizai/cogs/board.py`

**Interfaces — Consumes:** `sync_board`、`BoardGateway`、`Debouncer`、`find_expired`、`sort_for_board`、`paginate_entries`、`Store`。**Produces:** 监听 `on_board_dirty(mode)`（经 `Debouncer(cfg.board_refresh_debounce_sec)` 合并）；每 60 秒的后台任务清理过期条目并派发 `board_dirty`。

- [ ] **Step 1: 核对 Discord 当前限制并记录** 查官方文档：一条消息最多能放多少个组件、按钮；据此确定 `board.max_entries_per_message`（每个条目一行：需求、发起人、时间、跳转卡片链接，右侧"人数 @ 房间名"链接按钮，对照用户截图 2 的布局），写回 `docs/PARAMETERS.md` 与 `settings.toml`，并在 `docs/DECISIONS.md` 记 D-010。若所固定的 discord.py 版本不支持 Components V2（`discord.ui.LayoutView`、`Section`），停下来问用户。
- [ ] **Step 2: 实现 `BoardGateway`** 的 Discord 版本（`exists` 通过 `fetch_message` 判断；总表消息发在 `board_channel_id`；空页显示 `board_empty_text`；标题含模式名与"更新于"相对时间；每个条目含到卡片的跳转链接和进房按钮，按钮文案为"{人数}人 @ {房间名}"，人数取实时语音人数）。
- [ ] **Step 3: 实现刷新** 收到 `board_dirty(mode)` → `Debouncer` → 取 `store.list_entries(mode)`，`sort_for_board` → `paginate_entries` → `sync_board`。
- [ ] **Step 4: 实现清理任务** 每 60 秒 `find_expired`，删除过期条目（卡片不动）并派发 `board_dirty`；条目对应的房间已不存在也一并清掉。
- [ ] **Step 5: 手动验证** 在 `docs/TESTING.md` 增"总表"一节：发命令后总表出现条目；人数变化后 5 秒内更新；房间空了条目消失；手动删掉总表消息 → 下次刷新自动重发；手动删掉卡片 → 机器人不报错；超过每页上限（可临时把配置调小）→ 自动分页；30 分钟超时（可临时调小到 1 分钟）清掉条目。
- [ ] **Step 6: 提交** `feat: live board with paging and expiry`

### Task 13: 房间面板 cog

**Files:** Modify `src/zaizai/cogs/panel.py`

**Interfaces — Consumes:** `Store.set_locked`、`Store.set_panel_message`、`Store.delete_entry_by_room`、事件 `room_created`。**Produces:** 面板消息（房间聊天里，@房主）：说明文字（`panel_help_text`）+ 两个按钮：🔓开/🔒锁、组队已满；`/panel` 命令重新召唤面板（只在受管房间的聊天里可用）。

- [ ] **Step 1: 实现面板** 监听 `room_created` 发面板；按钮用持久化的动态按钮（`custom_id` 含房间 ID），机器人启动时注册，**重启后按钮仍可点**；只有房主能点，其他人收到仅自己可见的提示。
- [ ] **Step 2: 实现开/锁** 锁住 = 对 `@everyone` 设置 `connect=False`（已在房间里的人不受影响，房主保留连接权限）；再点还原；同步 `store.set_locked`，并更新按钮文案。
- [ ] **Step 3: 实现组队已满** `store.delete_entry_by_room` 后派发 `board_dirty`；无条目时提示"当前没有组队信息"。
- [ ] **Step 4: 实现 `/panel`**
- [ ] **Step 5: 手动验证** 在 `docs/TESTING.md` 增"面板"一节：非房主点按钮被拒；锁后另一账号进不来；解锁后能进；组队已满后总表条目消失而卡片保留；**重启机器人后按钮仍可点**；面板被手动删后 `/panel` 能重发。
- [ ] **Step 6: 提交** `feat: room control panel with lock and full buttons`

### Task 14: 广告位、文案与管理指令

**Files:** Create `src/zaizai/settings_view.py`、`tests/test_settings_view.py`；Modify `src/zaizai/cogs/admin.py`、`src/zaizai/cogs/lfg.py`

**Interfaces — Consumes:** `Store.get_setting`/`set_setting`、`Config`。**Produces:**
- `effective_setting(store: Store, cfg: Config, key: str, channel_id: int | None = None) -> str | bool | None`，支持键：`card.ad_text`、`card.footer_text`、`card.delete_original`（后者先查 `card.delete_original.<channel_id>` 覆盖，再查全局覆盖，最后回落到配置默认值）。
- 斜杠指令：`/motto <文字>`、`/ad <文字>`（文字为 `clear` 表示清空）、`/setting delete_original <on|off> [频道]`；仅限"管理服务器"权限（临时做法）。

- [ ] **Step 1: 写失败测试**：`test_falls_back_to_config_default`；`test_store_override_wins`；`test_channel_override_beats_global`；`test_clear_returns_none`；`test_delete_original_parses_on_off`。
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现 `effective_setting` 与三个斜杠指令**，设置写入 `Store`（重启后仍在）。
- [ ] **Step 4: 把 `lfg` cog 接入** `effective_setting`（广告位、页脚、删除原消息开关）。
- [ ] **Step 5: 运行确认通过** `pytest -v`；再在测试服务器验证三个指令即时生效、重启后保留、无权限账号被拒。
- [ ] **Step 6: 提交** `feat: editable ad, footer and delete-original settings`

### Task 15: Docker 与运行说明

**Files:** Create `Dockerfile`、`docker-compose.yml`、`.env.example`、`README.md`（Modify，补运行说明）；Modify `docs/TESTING.md`

- [ ] **Step 1: 实现** `Dockerfile`（`python:3.12-slim`，只装 `requirements.txt`，入口 `python -m zaizai`）；`docker-compose.yml` 一个服务 `bot-main`，挂载 `./config:/app/config` 与 `./data:/app/data`，`env_file: .env`，环境变量 `ZAIZAI_CONFIG=/app/config/settings.toml`、`ZAIZAI_DB_PATH=/app/data/zaizai.db`；注释里给出第二个服务（拆分用）的示例：不同令牌、不同数据文件、不同 `ZAIZAI_CONFIG`；`.env.example` 只含 `DISCORD_TOKEN=`。
- [ ] **Step 2: 本地测试配置** 说明用 `.env.dev` + `config/settings.dev.toml`（测试机器人令牌、测试服务器 ID）运行：`docker compose --env-file .env.dev up --build`。
- [ ] **Step 3: README** 写清楚：在开发者后台建机器人、开启 Message Content Intent、需要的权限（管理频道、移动成员、发送消息、嵌入链接、读取消息历史）、填 `settings.toml` 的 ID、本地与 VPS 的启动命令。
- [ ] **Step 4: 验证** `docker compose build` 成功；容器启动后在测试服务器过一遍 `docs/TESTING.md` 全部清单；`pytest -v` 全部通过。
- [ ] **Step 5: 更新** `docs/HANDOFF.md`、`docs/TODO.md`，提交 `chore: docker deployment and run instructions`
