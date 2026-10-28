# 可调参数表（PARAMETERS）

这是机器人所有"可调数值/开关/文案"的唯一来源。以后想调整，直接改这里的「当前值」列。
机器人实现时会从配置文件读取这些值，配置文件的键名与本表「键名」一致（读取方式见 `docs/DECISIONS.md`，尚未确定）。

状态说明：`建议值` = 我先给的初始值，需要你按实际情况调；`待查证` = 依赖 Discord 官方限制，写 spec 时核实；`已确认` = 你说过的。

_最后更新：2026-10-28（已加入房间控制面板、房间空了直接删除）_

## 1. 组队命令

| 键名 | 说明 | 当前值 | 状态 |
|---|---|---|---|
| `commands.ranked` | 排位组队频道的命令 | `!pw` | 已确认 |
| `commands.match` | 匹配组队频道的命令 | `!pp` | 已确认 |
| `commands.other` | 其他游戏频道的命令 | （未定） | 待确认 |
| `commands.accept_fullwidth` | 是否同时识别全角 `！` | `true` | 已确认 |
| `commands.need_voice` | 不在语音房间时是否拒绝并提示 | `true` | 已确认 |
| `commands.need_voice_msg` | 拒绝时的提示文字 | 请先加入语音房间再发组队信息 | 建议值 |
| `commands.allow_in_room_chat` | 是否也允许在房间自带的文字聊天里发命令（模式由房间所在分类决定） | `true` | 已确认（来自你的面板截图） |

## 2. 玩家消息下方的卡片

| 键名 | 说明 | 当前值 | 状态 |
|---|---|---|---|
| `card.delete_original` | 发卡片后是否删除玩家的原消息（开关，可按频道分别设置） | `false` | 已确认（默认值为建议值） |
| `card.after_entry_end` | 条目消失后，玩家消息下面的卡片怎么处理：`keep` 保留不处理 / `delete` 删除 | `keep` | 已确认 |
| `card.show_requirement` | 显示需求 | `true` | 已确认 |
| `card.show_board_link` | 显示"找人组队看这里"（链接到信息组队频道） | `true` | 已确认 |
| `card.show_host` | 显示发起人和时间 | `true` | 已确认 |
| `card.ad_enabled` | 是否显示广告位 | `true` | 已确认 |
| `card.ad_text` | 广告位文字（支持链接） | （待填） | 待确认 |
| `card.footer_text` | 底部自定义文字（用指令可修改） | （待填） | 待确认 |

## 3. 信息组队总表（每种模式一条固定消息，原地编辑）

| 键名 | 说明 | 当前值 | 状态 |
|---|---|---|---|
| `board.entry_timeout_min` | 条目超过多少分钟没有更新就清掉（"x 分钟"） | `30` | 建议值 |
| `board.remove_when_room_empty` | 房间空了立即清掉条目 | `true` | 已确认 |
| `board.refresh_debounce_sec` | 合并短时间内多次变化，最多每隔几秒编辑一次 | `5` | 建议值 |
| `board.max_entries_per_message` | 一条消息最多放多少个条目，超出就分页/拆条 | `10` | 待查证 |
| `board.empty_text` | 没有条目时显示的文字 | 当前没有活跃的信息。 | 已确认 |
| `board.show_member_count` | 条目右侧显示"人数 @ 房间名"按钮 | `true` | 已确认 |

## 4. 临时语音房间（加入即创建）

| 键名 | 说明 | 当前值 | 状态 |
|---|---|---|---|
| `voice.name_template` | 房间名模板，`{n}` 为序号 | `排位房 {n}` / `匹配房 {n}` / `其他房 {n}` | 建议值 |
| `voice.default_user_limit` | 新房间默认人数上限，0 为不限 | （待定） | 待确认 |
| `voice.empty_delete_delay_sec` | 房间空了多少秒后删除（给掉线重连留时间；设为 0 即立即删除） | `30` | 建议值 |
| `voice.reuse_empty_rooms` | 空房间是否留着复用（你已决定：空了直接删除，不复用） | `false` | 已确认 |
| `voice.category_max_channels` | 每个分类最多放多少个房间，超出自动开新分类 | `45` | 待查证（Discord 上限为 50，留余量） |
| `voice.create_queue_interval_ms` | 创建/删除频道的排队间隔（你说建房不太会堵，瓶颈在发组队信息，所以这项不用太严） | `500` | 建议值 |

## 5. 房间控制面板（房间建好后，机器人在房间的文字聊天里发一条，@房主）

| 键名 | 说明 | 当前值 | 状态 |
|---|---|---|---|
| `panel.enabled` | 建房后是否自动发控制面板 | `true` | 已确认 |
| `panel.owner_permissions` | 房主权限：只有开/锁，不能改名、改人数、踢人 | `lock_only` | 已确认 |
| `panel.button_lock` | 🔓开/🔒锁 按钮（锁住后别人不能再加入） | `true` | 已确认 |
| `panel.button_full` | "组队已满"按钮：把该房间的组队信息从卡片/总表里移除 | `true` | 已确认 |
| `panel.button_refresh` | "刷新面板"按钮（第一版不做） | `false` | 已确认 |
| `panel.button_crosshair` | "准星"按钮（第一版不做，用途待你说明） | `false` | 已确认 |
| `panel.recall_command` | 重新召唤面板的指令 | `/panel` | 待确认 |
| `panel.help_text` | 面板上的说明文字 | （照截图：命令可在此发送；点"组队已满"移除组队信息；/panel 重新召唤） | 待确认 |

## 6. 以后拆分成多个机器人时用到

| 键名 | 说明 | 当前值 | 状态 |
|---|---|---|---|
| `modules.enabled` | 当前机器人启用哪些功能模块 | 全部 | 已确认 |
| `modules.mode_scope` | 本机器人负责哪些模式（排位/匹配/其他） | 全部 | 已确认 |


> 说明：同一玩家的发命令间隔，由 Discord 频道自带的慢速模式（slowmode）控制，机器人不再单独限制。需求文字只按 Discord 的字数上限自动截断。
