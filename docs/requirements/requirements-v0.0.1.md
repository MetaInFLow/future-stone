# Future Stone Requirements v0.0.1

## 背景

LifeOS v1.1 定义了 Simulation Engine：推演我。它不是问 AI “我该怎么选”，而是构造多个“我”和多个世界视角，让用户在选择前看见不同版本的自己。

## P0

- 输入场景描述、讨论问题、世界数量、模拟轮次、Avatar、NPC 角色。
- 后端生成多条时间线、NPC、逐轮互动事件、skill run、decision trace 和 report。
- 前端用力导图和过程面板展示完整链路。
- 输出 JSON/JSONL artifact，便于后续进入 LifeOS 审阅和 PiAgent runner。

## Non-goals

- 第一版不做真实文件上传解析。
- 第一版不直接写 LifeOS Source。
- 第一版不承诺真实预测准确率。
- 第一版不复制 MiroFish 源码。

