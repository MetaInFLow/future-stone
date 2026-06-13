from __future__ import annotations

import json
from typing import Any, Protocol

from .llm_client import OpenAICompatibleJSONClient
from .schemas import SimulationEvent, SimulationRequest, World


class SkillRunner(Protocol):
    source: str
    model: str

    def run(
        self,
        world: World,
        round_index: int,
        events: list[SimulationEvent],
        request: SimulationRequest,
    ) -> dict[str, Any]:
        pass


class ReplaySkillRunner:
    model = "deterministic"

    def __init__(self, fallback_reason: str = "") -> None:
        self.fallback_reason = fallback_reason
        self.source = "replay-fallback" if fallback_reason else "replay"

    def run(
        self,
        world: World,
        round_index: int,
        events: list[SimulationEvent],
        request: SimulationRequest,
    ) -> dict[str, Any]:
        score = world.pressure_level + sum(event.impact for event in events)
        has_mainline_signal = any(
            "LifeOS" in variable or "demo" in variable for variable in world.external_variables
        )
        if score >= 6 and has_mainline_signal:
            decision = "参加"
        elif score <= -2:
            decision = "不参加"
        else:
            decision = "条件参加"
        return {
            "decision": decision,
            "rationale": (
                f"{world.title} 的主张是 {decision}。依据是外部变量、NPC 压力、"
                "长期主义视角和现实约束共同评分。"
            ),
            "confidence": max(0.35, min(0.92, 0.58 + score / 30)),
            "decision_basis": [
                f"外部变量：{', '.join(world.external_variables)}",
                f"世界张力：{world.dominant_tension}",
                "当前的我：偏向把高密度事件转成可展示产物",
                "长期主义的我：只接受能沉淀 LifeOS 主线资产的投入",
                "反方的我：警惕为了比赛而比赛、为了叙事而牺牲 M1",
            ],
            "self_model_refs": [
                "lifeos://avatar/decision-factors",
                "lifeos://avatar/boundary/human-decides",
            ],
            "_source": self.source,
            "_model": self.model,
            "_fallback_reason": self.fallback_reason,
        }


class LLMSkillRunner:
    source = "llm"

    def __init__(self, client: OpenAICompatibleJSONClient) -> None:
        self.client = client
        self.model = client.model

    def run(
        self,
        world: World,
        round_index: int,
        events: list[SimulationEvent],
        request: SimulationRequest,
    ) -> dict[str, Any]:
        fallback = ReplaySkillRunner().run(world, round_index, events, request)
        try:
            payload = self.client.complete_json(
                system_prompt=(
                    "你是 Future Stone 的 LifeOS SkillRunner。"
                    "你基于 Avatar 的决策偏好进行推演，只输出 JSON。"
                    "你不能替人做最终决定，只能输出可审阅的模拟判断、依据和置信度。"
                ),
                user_prompt=json.dumps(
                    {
                        "question": request.question,
                        "avatars": request.avatars,
                        "world": world.model_dump(mode="json"),
                        "round_index": round_index,
                        "npc_events": [event.model_dump(mode="json") for event in events],
                        "required_json_schema": {
                            "decision": "参加 | 不参加 | 条件参加",
                            "rationale": "为什么这样判断",
                            "confidence": "0.0-1.0 number",
                            "decision_basis": ["逐条依据，必须具体引用 world 或 npc event"],
                            "self_model_refs": ["lifeos://..."],
                        },
                    },
                    ensure_ascii=False,
                ),
            )
        except RuntimeError as exc:
            return ReplaySkillRunner(fallback_reason=str(exc)).run(
                world, round_index, events, request
            )
        normalized = normalize_skill_payload(payload, fallback=fallback)
        normalized["_source"] = self.source
        normalized["_model"] = self.model
        normalized["_fallback_reason"] = ""
        return normalized


def select_skill_runner(request: SimulationRequest) -> SkillRunner:
    if request.runner in {"llm", "piagent"}:
        client = OpenAICompatibleJSONClient.from_env()
        if client:
            return LLMSkillRunner(client)
        return ReplaySkillRunner(
            fallback_reason="LLM_API_KEY or OPENAI_API_KEY is not configured."
        )
    return ReplaySkillRunner()


def normalize_skill_payload(payload: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    decision = payload.get("decision")
    if decision not in {"参加", "不参加", "条件参加"}:
        decision = fallback["decision"]
    return {
        "decision": decision,
        "rationale": str(payload.get("rationale") or fallback["rationale"]),
        "confidence": bound_float(payload.get("confidence"), fallback["confidence"], 0.0, 1.0),
        "decision_basis": normalize_string_list(
            payload.get("decision_basis"), fallback["decision_basis"]
        ),
        "self_model_refs": normalize_string_list(
            payload.get("self_model_refs"), fallback["self_model_refs"]
        ),
    }


def normalize_string_list(value: Any, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return fallback
    items = [str(item).strip() for item in value if str(item).strip()]
    return items or fallback


def bound_float(value: Any, fallback: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = fallback
    return round(max(minimum, min(parsed, maximum)), 2)
