from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class SceneInput(BaseModel):
    description: str = Field(min_length=1)
    files: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class SimulationRequest(BaseModel):
    scene: SceneInput
    question: str = Field(min_length=1)
    world_count: int = 12
    rounds: int = 3
    avatars: list[str] = Field(default_factory=lambda: ["AnthonyFan.LifeOS"])
    npc_roles: list[str] = Field(default_factory=lambda: ["参赛选手", "家人", "评委"])
    runner: Literal["replay", "piagent"] = "replay"

    @field_validator("world_count")
    @classmethod
    def bound_world_count(cls, value: int) -> int:
        return max(1, min(value, 100))

    @field_validator("rounds")
    @classmethod
    def bound_rounds(cls, value: int) -> int:
        return max(1, min(value, 20))

    @field_validator("avatars")
    @classmethod
    def ensure_avatar(cls, value: list[str]) -> list[str]:
        return value or ["AnthonyFan.LifeOS"]

    @field_validator("npc_roles")
    @classmethod
    def ensure_npc_roles(cls, value: list[str]) -> list[str]:
        return value or ["现实约束者"]


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    detail: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str
    weight: float = 1.0


class ScenarioGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class World(BaseModel):
    id: str
    title: str
    summary: str
    external_variables: list[str]
    pressure_level: int
    dominant_tension: str


class Npc(BaseModel):
    id: str
    world_id: str
    role: str
    name: str
    stance: str
    influence: int
    goal: str


class SimulationEvent(BaseModel):
    id: str
    world_id: str
    round_index: int
    npc_id: str
    npc_role: str
    npc_message: str
    avatar_response: str
    impact: int
    evidence_refs: list[str]
    timestamp: str = Field(default_factory=utc_now)


class SkillRun(BaseModel):
    id: str
    world_id: str
    round_index: int
    skill_ref: str
    runner: str
    input_summary: str
    output_decision: str
    output_rationale: str
    confidence: float
    timestamp: str = Field(default_factory=utc_now)


class DecisionTrace(BaseModel):
    id: str
    world_id: str
    round_index: int
    decision: str
    skill_ref: str
    decision_basis: list[str]
    npc_effects: list[str]
    self_model_refs: list[str]
    confidence: float


class Progress(BaseModel):
    status: Literal["created", "running", "completed", "failed"] = "created"
    completed_steps: int = 0
    total_steps: int = 0
    current_step: str = ""
    updated_at: str = Field(default_factory=utc_now)


class Report(BaseModel):
    title: str
    question: str
    recommended_path: str
    timeline_count: int
    decision_distribution: dict[str, int]
    decisive_factors: list[str]
    risks: list[str]
    opportunities: list[str]
    summary: str


class StoryMap(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class SimulationResult(BaseModel):
    request: SimulationRequest
    scenario_graph: ScenarioGraph
    worlds: list[World]
    npcs: list[Npc]
    progress: Progress
    events: list[SimulationEvent]
    skill_runs: list[SkillRun]
    decision_traces: list[DecisionTrace]
    report: Report
    story_map: StoryMap

