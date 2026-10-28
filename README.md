# zaizai-community

玩家社区 Discord 组队机器人（Python + discord.py，Docker 部署）。功能：临时语音房间、`!pw` / `!pp` 组队命令与卡片、实时总表、房间面板（锁房/组队已满）、管理指令（`/motto`、`/ad`、`/setting`）。

- GitHub: https://github.com/Luhaoyang0207/zaizai-community
- 参数表：`docs/PARAMETERS.md`；设计：`docs/superpowers/specs/2026-10-28-zaizai-bot-design.md`

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

## 4. 测试

```
pip install -r requirements-dev.txt
python -m pytest
```

自动化测试不联网。需要真实服务器的人工清单见 `docs/TESTING.md`。

## For AI agents

Start with `AGENTS.md`, then `docs/HANDOFF.md` and `docs/DECISIONS.md`.
