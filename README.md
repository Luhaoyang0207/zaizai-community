# zaizai-community

玩家社区 Discord 组队机器人（Python + discord.py，Docker 部署）。功能：临时语音房间、`!pw` / `!pp` 组队命令与卡片、实时总表、房间面板（锁房/组队已满）、管理指令（`/motto`、`/ad`、`/setting`）。

- GitHub: https://github.com/Luhaoyang0207/zaizai-community
- 参数表：`docs/PARAMETERS.md`；设计：`docs/superpowers/specs/2026-10-28-zaizai-bot-design.md`
- 功能规则见下一节；每次改动记在文末「改动记录」。

## 功能规则（机器人现在怎么工作）

> 这一节描述的是**当前**行为，改了功能就同步改这里。括号里是对应的配置项（`config/settings.toml`），数值写的是默认值。

### 三种模式

| 模式 | 命令 | 总表 | 配置节 |
|---|---|---|---|
| 排位 | `!pw` | 排位总表 | `[modes.ranked]` |
| 匹配 | `!pp` | 匹配总表 | `[modes.unrated]` |
| 其他游戏 | 未定（`commands.other` 为空 = 关闭） | 命令为空时没有总表 | `[modes.other]` |

### 临时语音房间

1. 玩家进入某模式的「创造房间」入口语音频道 → 机器人新建一个房间，把他移进去，他就是房主。
2. 房间名按模板取最小的空号：`排位房 1`、`排位房 2`……（`voice.name_template`）。人数上限默认不限（`voice.default_user_limit = 0`）。
3. 房间按顺序放进配置的分类（`category_ids`），每个分类最多 45 个（`voice.category_max_channels`）；全部满了机器人自动新开分类，名字是第一个分类名加 " 2"、" 3"，权限复制自第一个分类。新房间的权限和所在分类一致。
4. 房间没人了 → 它的组队信息**立刻**从总表消失；**30 秒**后房间被删除（`voice.empty_delete_delay_sec`），这 30 秒内有人回来就不删。空房间不复用。
5. 机器人重启时会核对：记录里已不存在的房间被清掉；受管分类里有人但没记录的语音频道被认领（第一个人当房主）；**受管分类里没人、没记录的语音频道被删除**（入口频道除外）。所以这些分类只能给机器人用。

### 组队命令

**在哪里发：**

| 位置 | 接受的命令 |
|---|---|
| 服务器里**任何语音频道**的聊天（临时房间或常驻频道，如闲聊；舞台频道、子区不算） | 所有已启用的命令；`!pw` 进排位总表，`!pp` 进匹配总表（`commands.allow_in_room_chat`） |
| 排位组队文字频道 | 只认 `!pw`，其他命令忽略 |
| 匹配组队文字频道 | 只认 `!pp`，其他命令忽略 |
| 其他频道 | 不响应 |

**怎么写：** `!pw 铂钻 3=2`。全角 `！pw`、`! pw`（感叹号后有空格）、`!PW` 都认（`commands.accept_fullwidth`）；`!pwn` 不算；`!pw` 后面不写字也可以（显示"组队中"）。

**条件：** 发命令的人必须**在某个语音频道里**（入口频道不算），否则机器人回复"请先加入语音房间再发组队信息"（`commands.need_voice`、`commands.need_voice_msg`）。频率限制交给频道的慢速模式，机器人不额外限制。

**结果：**
- 机器人在玩家消息下面回一张**卡片**：需求、"找人组队看这里"总表链接、发起人和时间、广告位、底部文字（`card.*`）。
- 总表里出现一条组队信息，挂在发命令的人**当前所在的语音频道**上（不是发消息的那个聊天）。
- **一个语音频道只有一条**：再发一次只更新这一条；同一频道先 `!pw` 后 `!pp`，信息从排位总表移到匹配总表。
- 开了"删除原消息"（`card.delete_original`，默认关）时，发出卡片后删掉玩家的命令消息。

### 信息组队总表

- 总表频道里每种模式一条固定消息，原地编辑；最新的在最上面；每条消息最多 10 条信息（`board.max_entries_per_message`，最大 12），多了自动分成多条。
- 每条信息：需求、发起人、时间、"查看卡片"链接，右边按钮"3人 @ 排位房 2"，点了进那个语音频道（`board.show_member_count`）。没有信息时显示"当前没有活跃的信息。"（`board.empty_text`）。
- 最多每 5 秒更新一次（`board.refresh_debounce_sec`），内容没变就不编辑；"更新于"是内容最后一次变化的时间。
- 信息消失的情况（任一）：那个语音频道没人了（`board.remove_when_room_empty`）、30 分钟没更新（`board.entry_timeout_min`）、房主点"组队已满"、频道被删。信息消失后**卡片保留**不动。
- 总表消息被人手动删了 → 几秒内自动重发。
- 命令为空的模式（目前是"其他游戏"）不发总表。

### 房间控制面板（只在机器人建的临时房间里）

- 建房后机器人在房间聊天里 @房主，下面是"房间控制面板"卡片（说明文字 `panel.help_text`）和两个按钮。**只有房主能点**，别人点会收到仅自己可见的提示。
- **🔓开 / 🔒锁**：锁住后别人进不来，已经在房间里的人不受影响，房主自己随时能进。即使分类里某个身份组被允许连接，锁房后这个身份组也进不来；解锁时恢复成分类原来的设置。
- **组队已满**：把这个房间的组队信息从总表移除，卡片保留。
- `/panel`：在临时房间的聊天里、人在这个房间里时，可以重新发一份面板（旧的被删掉）。
- 机器人重启后，旧面板上的按钮仍然能点。
- 常驻语音频道（不是机器人建的）**没有面板**：机器人不改名、不锁、不删这些频道，只在上面挂组队信息。

### 管理指令（需要「管理服务器」权限）

| 指令 | 作用 |
|---|---|
| `/ad <文字>` | 设置卡片广告位文字；写 `clear` 清空 |
| `/motto <文字>` | 设置卡片底部文字；写 `clear` 清空 |
| `/setting delete_original <on/off> [频道]` | 开关"发卡片后删除原消息"；指定频道只对该频道生效 |

设置立刻生效，存在机器人的数据库里，重启后保留。没有权限的人使用会收到"需要「管理服务器」权限"。

### 出错时

- 机器人缺少某个权限：日志里写明缺什么，并在总表频道提示**一次**（同一类问题不重复提示）。
- Discord 临时出错：自动重试 3 次，还不行就跳过这一次，机器人不会退出。
- 卡片、面板、总表被人删了：不报错，需要时自动重建。

## 1. 在 Discord 开发者后台建机器人

到 https://discord.com/developers/applications 建**两个**应用：一个正式、一个测试（D-004：测试和线上用不同令牌、不同服务器）。每个应用：

1. Bot 页：Reset Token 取得令牌（只放进 `.env` / `.env.dev`，不要提交、不要发给别人）。
2. Bot 页 → Privileged Gateway Intents，打开：
   - **Message Content Intent**（读 `!pw` 等命令文字）
   - **Server Members Intent**（机器人用到成员信息）
3. OAuth2 → URL Generator，scope 选 `bot` 和 `applications.commands`，权限勾选：
   - View Channels、Connect（看见并连接语音房间）
   - **Manage Channels**（建/删语音房间、复制分类；锁房按钮改的是房间的 connect 权限覆盖，多数设置下这一项就够）
   - **Manage Roles / 管理身份组**（有条件需要：锁房按钮写权限覆盖时，部分服务器设置会要求；缺少时点锁会失败并在管理频道提示）
   - Move Members（把玩家移入新建的房间）
   - Send Messages、Embed Links、Read Message History（发卡片、总表、面板）
   - Manage Messages（仅当开启 `card.delete_original` 删除原消息时需要）
4. 用生成的链接把机器人邀请到对应服务器（正式机器人 → 正式服，测试机器人 → 测试服）。

## 2. 填配置

复制 `.env.example` 为 `.env`，写入 `DISCORD_TOKEN=<令牌>`。

在 `config/settings.toml` 填 ID（含服务器 ID、总表频道、每个模式的入口频道 / 组队频道 / 分类），位置和说明见 `docs/PARAMETERS.md` 第 7 节「频道 ID」。其余参数也以该表为准。

注意：**受管分类必须专用于机器人**。分类里任何其他空的语音频道会在机器人重启对账时被删除。

## 3. 启动

线上（VPS）：

首次需要：先 `cp .env.example .env` 并填入令牌——`.env` 不存在时 `docker compose up` 会报 "env file not found"。

Linux 上容器以 uid 1000 运行，`./data` 必须对它可写，`./config` 必须可读。一次性设置：

```
mkdir -p data && sudo chown -R 1000:1000 data
```

或者不改属主，在 `.env` 里设 `ZAIZAI_UID=$(id -u)`、`ZAIZAI_GID=$(id -g)` 的实际数值（宿主用户的 `id -u` / `id -g`）。否则 SQLite 打不开，容器会因 `restart: unless-stopped` 反复重启。

```
docker compose up -d --build
docker compose logs -f bot-main
```

### 本地测试（测试机器人 + 测试服务器）

1. `cp config/settings.dev.toml.example config/settings.dev.toml`，填入测试服务器的 ID。
2. 新建 `.env.dev`（已被 git 忽略，不要提交）：

```
DISCORD_TOKEN=<测试机器人令牌>
ZAIZAI_ENV_FILE=.env.dev
ZAIZAI_CONFIG_FILE=settings.dev.toml
ZAIZAI_DB_FILE=dev.db
```

3. 启动：

```
docker compose -p zaizai-dev --env-file .env.dev up --build
```

`--env-file` 让 compose 改用 `.env.dev` 的令牌、`settings.dev.toml` 和 `data/dev.db`；`-p zaizai-dev` 使其与线上栈分开。

### 拆分成多个机器人

见 `docker-compose.yml` 末尾被注释的第二个服务示例：不同令牌（另一个 env 文件）、不同数据文件、不同 `ZAIZAI_CONFIG`（用 `modules.enabled` / `modules.mode_scope` 限定职责）。

注意：
- 每个实例都会注册自己的 `/panel`、`/ad`、`/motto`（以及 `/setting`），斜杠菜单里会出现重复项。额外的实例请在 `modules.enabled` 里去掉 `admin` 和 `panel`，只留一个实例负责它们。
- `/ad`、`/motto`、`/setting` 的设置存在各实例自己的 SQLite 文件里，不会共享：哪个实例发卡片，就要在哪个实例上设置。

## 4. 测试

```
pip install -r requirements-dev.txt
python -m pytest
```

自动化测试不联网。需要真实服务器的人工清单见 `docs/TESTING.md`。

## 改动记录

> 每次改动都在最上面加一行：日期、改了什么（玩家/管理员能感觉到的变化）、提交。决策原因见 `docs/DECISIONS.md` 对应编号。

### 2026-10-29
- 改动记录和功能规则写进 README，`AGENTS.md` 要求以后每次改动都更新这两节。
- **任何语音频道**的聊天里都能发 `!pw` / `!pp`，包括常驻频道；组队文字频道仍只认本模式命令；发命令的人在任何语音频道里即可（D-014）。`507918c`
- 修复：在排位房里发 `!pp` 这类跨模式信息时，清空房间、点"组队已满"后对应总表会残留旧信息。`e2021a4`
- 面板说明文字改用卡片（embed）显示，标题"房间控制面板"，@房主保留在卡片上方。`3084eee`
- `config/settings.toml` 每一项都加了中文说明。`5e7f563`

### 2026-10-28
- 每个模式可以配置多个分类：`category_ids = [...]`，按顺序使用（D-013）。`87d3b3f`
- 匹配模式在配置里的名字从 `match` 改为 `unrated`，玩家看到的不变（D-012）。`199f187`
- 第一版完成并合并（`dee38aa`）：临时语音房间、`!pw` / `!pp` 卡片、实时总表、房间面板、管理指令、Docker 部署。上线前的整体审查修复：降低总表接口调用、断线重连后重新核对房间、无效配置值启动报错、锁房同时拦住被允许连接的身份组、手动删除的总表自动重发（D-010、D-011）。

## For AI agents

Start with `AGENTS.md`, then `docs/HANDOFF.md` and `docs/DECISIONS.md`.
