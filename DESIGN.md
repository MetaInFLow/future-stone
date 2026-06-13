# Design

Future Stone 是工作台，不是营销页。

## UI 原则

- 第一屏就是可用推演台。
- 左侧输入和链路，右侧是 simulation canvas。
- 主图使用 force-directed layout，节点可点击查看详情。
- 每次推演必须同时展示：时间线、NPC 互动、skill run、决策依据、报告。
- 色彩使用中性底色 + 少量青绿、蓝、紫、琥珀、玫红区分节点类型，避免单一色系。

## 节点类型

- `question`
- `scene`
- `avatar`
- `self_lens`
- `npc_role`
- `world`
- `npc`
- `decision`

