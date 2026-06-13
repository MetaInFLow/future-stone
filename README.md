# Future Stone

Future Stone 是 LifeOS 的 **Decision Simulation Agent**。

它把一个真实选择放进多条可能时间线里，生成世界、NPC、逐轮互动、LifeOS skill run、决策依据和最终报告。它借鉴 MiroFish 的五步体验，但核心目标不是预测世界，而是推演“我在不同世界中会变成什么样的人”。

## 核心链路

```text
场景描述 / 文件 / 问题
-> Graph Build：抽取 Avatar、NPC、变量、讨论问题
-> Environment Setup：按 world_count 生成多条时间线
-> Simulation Loop：按 world × round 跑 LifeOS skill
-> Report：汇总结论、风险、机会、依据
-> Interaction：点开节点查看每轮过程
```

## 本地启动

```bash
pnpm install
pnpm dev:api
pnpm dev:web
```

默认地址：

- Backend API: `http://localhost:5055`
- Web UI: `http://localhost:5177`

## 验证

```bash
pnpm verify
```

## 输入示例

```json
{
  "scene": {
    "description": "要不要参加黑客松？"
  },
  "question": "Anthony 和 Neil 是否应该参加这次黑客松？",
  "world_count": 12,
  "rounds": 3,
  "avatars": ["AnthonyFan.LifeOS", "Neil.LifeOS"],
  "npc_roles": ["参赛选手", "家人", "评委"],
  "runner": "replay"
}
```

## 输出产物

每次 simulation 写入 `runtime/simulations/<simulation_id>/`：

- `simulation_request.json`
- `scenario_graph.json`
- `worlds.json`
- `npcs.json`
- `progress.json`
- `simulation_events.jsonl`
- `skill_runs.jsonl`
- `decision_traces.jsonl`
- `report.json`
- `story_map.json`

## MiroFish 借鉴边界

本项目借鉴 MiroFish 的五步产品链路和图谱/报告/互动呈现方式，不复制 MiroFish AGPL-3.0 代码。Future Stone 的 runtime 是 LifeOS skill / PiAgent 适配层，而不是 CAMEL/OASIS 社交仿真。

