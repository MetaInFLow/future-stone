# Architecture

## 一句话

Future Stone 是一个 Web + Backend 项目：前端展示多时间线沙盘，后端生成和持久化可审阅的 LifeOS 决策推演产物。

## 模块

```text
apps/studio-web
  Vue 3 + D3，负责输入、力导图、事件流、skill run、report 展示

services/backend-api
  Flask API，负责 simulation 创建、运行、artifact 查询

services/backend-api/app/modules/simulation
  schemas.py：输入输出协议
  simulation_loop.py：世界/NPC/事件/skill run/report 生成
  repository.py：JSON/JSONL artifact 持久化
  use_cases.py：API 用例层
```

## Runner 策略

当前实现 `replay` runner，用确定性 mock 输出跑通端到端链路。后续接入 `piagent` 时，保持同一个 `SkillRun` 和 `DecisionTrace` schema：

```text
Future Stone request
-> PiAgent SkillRunner
-> LifeOS skill set
-> skill_runs.jsonl / decision_traces.jsonl
```

## 架构边界

- Future Stone 不直接写 LifeOS Source。
- 推演结果是 decision support，不是替用户决定。
- 所有长期记忆、Skill、身份或原则更新，必须进入 LifeOS 的审阅流程。
- MiroFish 只作为产品链路参考，不作为代码来源。

