# Future Stone Bootstrap Design

## 目标

做出 LifeOS Decision Simulation Agent 的最小端到端闭环：用户输入一个选择，系统生成多条时间线，逐轮跑 skill trace，并在前端看到过程和依据。

## 关键设计

- 产品名：Future Stone。
- Repo：`MetaInFLow/future-stone`。
- 后端：Flask + Pydantic + JSON/JSONL artifacts。
- 前端：Vue 3 + Vite + D3。
- Runner：先 `ReplaySkillRunner`，后续接 `PiAgentSkillRunner`。

## 与 MiroFish 的关系

借鉴五步体验：Graph Build、Environment Setup、Simulation Loop、Report、Interaction。核心 runner 不用 CAMEL/OASIS，替换为 LifeOS skill set。

