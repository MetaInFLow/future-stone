from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol

from .llm_client import OpenAICompatibleJSONClient
from .schemas import Npc, SimulationRequest, World

WORLD_PATTERNS = [
    ("赛题高度贴合 LifeOS", ["评委关注真实 demo", "现场资源密集", "传播机会强"], "使命与窗口"),
    ("赛题偏离主线", ["题目偏工具化", "demo 难以沉淀", "时间被切碎"], "方向偏离"),
    ("团队状态紧张", ["睡眠不足", "分工不稳", "外部承诺挤压"], "资源约束"),
    ("NPC 强烈支持", ["参赛者愿意共创", "评委期待叙事", "家人接受短期投入"], "关系助推"),
    ("外部反馈冷淡", ["用户不理解", "评委只看功能", "传播噪音高"], "市场误读"),
]


class ScenarioGenerator(Protocol):
    def generate(self, request: SimulationRequest) -> ScenarioGeneration:
        pass


@dataclass
class ScenarioGeneration:
    source: str
    model: str
    worlds: list[dict[str, Any]]
    npcs: list[dict[str, Any]]
    fallback_reason: str = ""


class ReplayScenarioGenerator:
    def __init__(self, fallback_reason: str = "") -> None:
        self.fallback_reason = fallback_reason

    def generate(self, request: SimulationRequest) -> ScenarioGeneration:
        worlds = replay_worlds(request)
        npcs = replay_npcs(worlds, request.npc_roles)
        return ScenarioGeneration(
            source="replay-fallback" if self.fallback_reason else "replay",
            model="deterministic",
            worlds=[world.model_dump(mode="json") for world in worlds],
            npcs=[npc.model_dump(mode="json") for npc in npcs],
            fallback_reason=self.fallback_reason,
        )


class LLMScenarioGenerator:
    def __init__(self, client: OpenAICompatibleJSONClient) -> None:
        self.client = client

    def generate(self, request: SimulationRequest) -> ScenarioGeneration:
        payload = self.client.complete_json(
            system_prompt=(
                "你是 Future Stone 的场景生成器。"
                "你只输出 JSON，不输出 markdown。"
                "你的任务是根据 LifeOS 的 Simulation Engine 思想生成多条可能时间线和 NPC。"
                "这些不是通用利弊分析，而是围绕 Avatar 在世界中的可能版本。"
            ),
            user_prompt=json.dumps(
                {
                    "scene": request.scene.model_dump(mode="json"),
                    "question": request.question,
                    "world_count": request.world_count,
                    "rounds": request.rounds,
                    "avatars": request.avatars,
                    "npc_roles": request.npc_roles,
                    "required_json_schema": {
                        "worlds": [
                            {
                                "title": "时间线名称",
                                "summary": "这个世界发生了什么",
                                "external_variables": ["影响决策的外部变量"],
                                "pressure_level": "1-5 integer",
                                "dominant_tension": "这个世界的核心张力",
                            }
                        ],
                        "npcs": [
                            {
                                "world_index": "1-based world index",
                                "role": "必须来自 npc_roles",
                                "name": "具体人物名",
                                "stance": "此 NPC 在该时间线中的立场",
                                "influence": "1-5 integer",
                                "goal": "此 NPC 想推动什么",
                            }
                        ],
                    },
                },
                ensure_ascii=False,
            ),
        )
        worlds = normalize_worlds(payload.get("worlds", []), request)
        npcs = normalize_npcs(payload.get("npcs", []), worlds, request)
        return ScenarioGeneration(
            source="llm",
            model=self.client.model,
            worlds=[world.model_dump(mode="json") for world in worlds],
            npcs=[npc.model_dump(mode="json") for npc in npcs],
        )


def select_scenario_generator(request: SimulationRequest) -> ScenarioGenerator:
    if request.runner in {"llm", "piagent"}:
        client = OpenAICompatibleJSONClient.from_env()
        if client:
            return LLMScenarioGenerator(client)
        return ReplayScenarioGenerator(
            fallback_reason="LLM_API_KEY or OPENAI_API_KEY is not configured."
        )
    return ReplayScenarioGenerator()


def replay_worlds(request: SimulationRequest) -> list[World]:
    worlds = []
    for index in range(request.world_count):
        pattern = WORLD_PATTERNS[index % len(WORLD_PATTERNS)]
        pressure = 2 + stable_int(f"{request.question}:{index}", 4)
        worlds.append(
            World(
                id=f"world-{index + 1:03d}",
                title=f"时间线 {index + 1:03d}",
                summary=f"{pattern[0]}：{request.question}",
                external_variables=pattern[1],
                pressure_level=pressure,
                dominant_tension=pattern[2],
            )
        )
    return worlds


def replay_npcs(worlds: list[World], roles: list[str]) -> list[Npc]:
    npcs = []
    for world in worlds:
        for index, role in enumerate(roles, start=1):
            influence = 1 + stable_int(f"{world.id}:{role}", 5)
            npcs.append(
                Npc(
                    id=f"{world.id}-npc-{index}",
                    world_id=world.id,
                    role=role,
                    name=f"{role}-{world.id[-3:]}",
                    stance=stance_for(role, world.dominant_tension, influence),
                    influence=influence,
                    goal=goal_for(role),
                )
            )
    return npcs


def normalize_worlds(raw_worlds: list[dict[str, Any]], request: SimulationRequest) -> list[World]:
    fallback_worlds = replay_worlds(request)
    worlds = []
    for index in range(request.world_count):
        raw = (
            raw_worlds[index]
            if index < len(raw_worlds) and isinstance(raw_worlds[index], dict)
            else {}
        )
        fallback = fallback_worlds[index]
        worlds.append(
            World(
                id=f"world-{index + 1:03d}",
                title=str(raw.get("title") or fallback.title),
                summary=str(raw.get("summary") or fallback.summary),
                external_variables=normalize_string_list(
                    raw.get("external_variables"), fallback.external_variables
                ),
                pressure_level=bound_int(raw.get("pressure_level"), fallback.pressure_level, 1, 5),
                dominant_tension=str(raw.get("dominant_tension") or fallback.dominant_tension),
            )
        )
    return worlds


def normalize_npcs(
    raw_npcs: list[dict[str, Any]], worlds: list[World], request: SimulationRequest
) -> list[Npc]:
    fallback = replay_npcs(worlds, request.npc_roles)
    by_key: dict[tuple[int, str], dict[str, Any]] = {}
    for raw in raw_npcs:
        if not isinstance(raw, dict):
            continue
        world_index = bound_int(raw.get("world_index"), 1, 1, len(worlds))
        role = str(raw.get("role") or "")
        if role in request.npc_roles:
            by_key[(world_index, role)] = raw

    npcs = []
    for fallback_npc in fallback:
        world_index = int(fallback_npc.world_id.split("-")[1])
        raw = by_key.get((world_index, fallback_npc.role), {})
        npcs.append(
            Npc(
                id=fallback_npc.id,
                world_id=fallback_npc.world_id,
                role=fallback_npc.role,
                name=str(raw.get("name") or fallback_npc.name),
                stance=str(raw.get("stance") or fallback_npc.stance),
                influence=bound_int(raw.get("influence"), fallback_npc.influence, 1, 5),
                goal=str(raw.get("goal") or fallback_npc.goal),
            )
        )
    return npcs


def normalize_string_list(value: Any, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return fallback
    items = [str(item).strip() for item in value if str(item).strip()]
    return items or fallback


def bound_int(value: Any, fallback: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(minimum, min(parsed, maximum))


def stable_int(seed: str, modulo: int) -> int:
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def stance_for(role: str, tension: str, influence: int) -> str:
    if "家人" in role:
        return "支持你做长期正确的事，但要求别牺牲身体和亲密关系"
    if "评委" in role:
        return "只认可能现场跑起来、能说清用户价值的 demo"
    if "参赛" in role:
        return "愿意一起冲刺，但希望目标明确、分工清楚"
    if influence >= 4:
        return f"强烈放大{tension}带来的机会与风险"
    return f"提醒{tension}不能被忽略"


def goal_for(role: str) -> str:
    if "家人" in role:
        return "保护长期节奏和关系成本"
    if "评委" in role:
        return "判断作品是否有真实用户价值"
    if "参赛" in role:
        return "在 48 小时内做出能讲清的作品"
    return "给 Avatar 决策增加现实压力"
