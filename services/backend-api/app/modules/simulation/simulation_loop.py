from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

from .generation import ReplayScenarioGenerator, ScenarioGenerator, select_scenario_generator
from .repository import write_json, write_jsonl
from .schemas import (
    DecisionTrace,
    GraphEdge,
    GraphNode,
    Npc,
    Progress,
    Report,
    ScenarioGraph,
    SimulationEvent,
    SimulationRequest,
    SimulationResult,
    SkillRun,
    StoryMap,
    World,
    utc_now,
)
from .skill_runner import SkillRunner, select_skill_runner

SELF_LENSES = [
    ("current-self", "当前的我", "按现有惯性做选择"),
    ("long-term-self", "长期主义的我", "从 3 年和 10 年后回看"),
    ("reality-self", "现实约束的我", "检查现金流、时间、资源和团队状态"),
    ("brave-self", "更勇敢的我", "去掉恐惧后的选择"),
    ("contrarian-self", "反方的我", "识别幻觉、自嗨和过度叙事"),
    ("mission-observer", "使命观察者", "判断是否靠近我是谁"),
]


def run_simulation(
    request: SimulationRequest,
    output_dir: Path,
    generator: ScenarioGenerator | None = None,
    skill_runner: SkillRunner | None = None,
) -> SimulationResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    scenario_graph = build_scenario_graph(request)
    selected_generator = generator or select_scenario_generator(request)
    selected_skill_runner = skill_runner or select_skill_runner(request)
    try:
        generation = selected_generator.generate(request)
    except RuntimeError as exc:
        generation = ReplayScenarioGenerator(fallback_reason=str(exc)).generate(request)

    worlds = [World.model_validate(world) for world in generation.worlds]
    npcs = [Npc.model_validate(npc) for npc in generation.npcs]
    progress = Progress(
        status="running",
        completed_steps=0,
        total_steps=len(worlds) * request.rounds,
        generation_source=generation.source,
        generation_model=generation.model,
        fallback_reason=generation.fallback_reason,
        skill_runner_source=selected_skill_runner.source,
        skill_runner_model=selected_skill_runner.model,
    )
    events: list[SimulationEvent] = []
    skill_runs: list[SkillRun] = []
    decision_traces: list[DecisionTrace] = []

    write_json(output_dir / "simulation_request.json", request)
    write_json(output_dir / "scenario_graph.json", scenario_graph)
    write_json(output_dir / "worlds.json", [world.model_dump(mode="json") for world in worlds])
    write_json(output_dir / "npcs.json", [npc.model_dump(mode="json") for npc in npcs])

    npc_by_world = {world.id: [npc for npc in npcs if npc.world_id == world.id] for world in worlds}
    for world in worlds:
        for round_index in range(1, request.rounds + 1):
            round_events = [
                build_event(world, npc, round_index, request) for npc in npc_by_world[world.id]
            ]
            events.extend(round_events)

            skill_run, trace = run_skill(
                world,
                round_index,
                round_events,
                request,
                selected_skill_runner,
                progress,
            )
            skill_runs.append(skill_run)
            decision_traces.append(trace)

            progress.completed_steps += 1
            progress.current_step = f"{world.title} / Round {round_index}"
            progress.updated_at = utc_now()
            write_json(output_dir / "progress.json", progress)
            write_jsonl(output_dir / "simulation_events.jsonl", events)
            write_jsonl(output_dir / "skill_runs.jsonl", skill_runs)
            write_jsonl(output_dir / "decision_traces.jsonl", decision_traces)

    progress.status = "completed"
    progress.updated_at = utc_now()
    report = compile_report(request, worlds, decision_traces)
    story_map = build_story_map(scenario_graph, worlds, npcs, decision_traces)

    write_json(output_dir / "progress.json", progress)
    write_json(output_dir / "report.json", report)
    write_json(output_dir / "story_map.json", story_map)

    return SimulationResult(
        request=request,
        scenario_graph=scenario_graph,
        worlds=worlds,
        npcs=npcs,
        progress=progress,
        events=events,
        skill_runs=skill_runs,
        decision_traces=decision_traces,
        report=report,
        story_map=story_map,
    )


def build_scenario_graph(request: SimulationRequest) -> ScenarioGraph:
    nodes = [
        GraphNode(id="question", label="讨论问题", type="question", detail=request.question),
        GraphNode(id="scene", label="场景", type="scene", detail=request.scene.description),
    ]
    edges = [GraphEdge(source="scene", target="question", label="frames")]

    for avatar in request.avatars:
        avatar_id = slug_id("avatar", avatar)
        nodes.append(GraphNode(id=avatar_id, label=avatar, type="avatar", detail="LifeOS avatar"))
        edges.append(GraphEdge(source=avatar_id, target="question", label="decides"))

    for lens_id, label, detail in SELF_LENSES:
        nodes.append(GraphNode(id=lens_id, label=label, type="self_lens", detail=detail))
        edges.append(GraphEdge(source=lens_id, target="question", label="evaluates"))

    for role in request.npc_roles:
        role_id = slug_id("npc-role", role)
        nodes.append(GraphNode(id=role_id, label=role, type="npc_role", detail="场景中会出现的人"))
        edges.append(GraphEdge(source=role_id, target="question", label="pressures"))

    return ScenarioGraph(nodes=nodes, edges=edges)


def build_event(
    world: World, npc: Npc, round_index: int, request: SimulationRequest
) -> SimulationEvent:
    message = (
        f"在{world.title}第 {round_index} 轮，{npc.name}（{npc.role}）带着目标"
        f"“{npc.goal}”进入讨论；TA 的立场是：{npc.stance}。"
    )
    response = (
        f"Avatar 记录 {npc.role} 的现实压力，把它和“{request.question}”放到"
        f"“{world.dominant_tension}”张力里评估。"
    )
    impact = npc.influence if "支持" in npc.stance or "机会" in npc.stance else -npc.influence
    return SimulationEvent(
        id=f"{world.id}-r{round_index}-{npc.id}",
        world_id=world.id,
        round_index=round_index,
        npc_id=npc.id,
        npc_role=npc.role,
        npc_message=message,
        avatar_response=response,
        impact=impact,
        evidence_refs=[
            "lifeos://skill/decision-simulation/input",
            "lifeos://principle/human-decides-ai-simulates",
        ],
    )


def run_skill(
    world: World,
    round_index: int,
    events: list[SimulationEvent],
    request: SimulationRequest,
    skill_runner: SkillRunner,
    progress: Progress,
) -> tuple[SkillRun, DecisionTrace]:
    output = skill_runner.run(world, round_index, events, request)
    runner_source = str(output.get("_source") or skill_runner.source)
    runner_model = str(output.get("_model") or skill_runner.model)
    fallback_reason = str(output.get("_fallback_reason") or "")
    if fallback_reason:
        progress.fallback_reason = merge_fallback_reason(progress.fallback_reason, fallback_reason)
        progress.skill_runner_source = runner_source
        progress.skill_runner_model = runner_model

    decision = str(output["decision"])
    rationale = str(output["rationale"])
    confidence = float(output["confidence"])
    decision_basis = [str(item) for item in output.get("decision_basis", [])]
    self_model_refs = [str(item) for item in output.get("self_model_refs", [])]
    skill_ref = f"lifeos://skill/decision-simulation/{runner_source}"
    skill_run = SkillRun(
        id=f"{world.id}-round-{round_index}-skill-run",
        world_id=world.id,
        round_index=round_index,
        skill_ref=skill_ref,
        runner=runner_source,
        input_summary=f"{request.question} / {world.summary}",
        output_decision=decision,
        output_rationale=rationale,
        confidence=round(confidence, 2),
    )
    trace = DecisionTrace(
        id=f"{world.id}-round-{round_index}-decision",
        world_id=world.id,
        round_index=round_index,
        decision=decision,
        skill_ref=skill_ref,
        decision_basis=decision_basis,
        npc_effects=[f"{event.npc_role}: {event.impact:+d}" for event in events],
        self_model_refs=self_model_refs,
        confidence=skill_run.confidence,
    )
    return skill_run, trace


def merge_fallback_reason(existing: str, new_reason: str) -> str:
    if not existing:
        return new_reason
    if new_reason in existing:
        return existing
    return f"{existing} | {new_reason}"


def compile_report(
    request: SimulationRequest, worlds: list[World], traces: list[DecisionTrace]
) -> Report:
    distribution = Counter(trace.decision for trace in traces)
    recommended_path = distribution.most_common(1)[0][0]
    return Report(
        title="Future Stone Decision Simulation Report",
        question=request.question,
        recommended_path=recommended_path,
        timeline_count=len(worlds),
        decision_distribution=dict(distribution),
        decisive_factors=[
            "是否服务 LifeOS 主线资产",
            "是否能在限定时间内形成可演示闭环",
            "NPC 压力是否暴露真实用户和评委反馈",
            "是否牺牲家庭、团队和长期节奏",
        ],
        risks=[
            "把黑客松误当成目标，而不是把它当成 Future Stone / LifeOS demo sprint",
            "宏大叙事过早扩张，M1 失焦",
        ],
        opportunities=[
            "用高压场景验证 Decision Simulation Agent",
            "把 Anthony + Neil + NPC 互动沉淀成可复用 skill trace",
        ],
        summary=(
            f"系统跑了 {len(worlds)} 条时间线、{len(traces)} 次 LifeOS skill 决策。"
            f"主路径是：{recommended_path}。这不是替人决定，而是给人可审阅的推演依据。"
        ),
    )


def build_story_map(
    scenario_graph: ScenarioGraph,
    worlds: list[World],
    npcs: list[Npc],
    traces: list[DecisionTrace],
) -> StoryMap:
    nodes = list(scenario_graph.nodes)
    edges = list(scenario_graph.edges)
    for world in worlds:
        nodes.append(
            GraphNode(
                id=world.id,
                label=world.title,
                type="world",
                detail=world.summary,
                data={"pressure_level": world.pressure_level, "tension": world.dominant_tension},
            )
        )
        edges.append(GraphEdge(source="question", target=world.id, label="branches"))

    for npc in npcs:
        nodes.append(
            GraphNode(
                id=npc.id,
                label=npc.name,
                type="npc",
                detail=f"{npc.role}: {npc.stance}",
                data={"role": npc.role, "influence": npc.influence},
            )
        )
        edges.append(GraphEdge(source=npc.world_id, target=npc.id, label="contains"))

    for trace in traces:
        trace_id = f"{trace.id}-node"
        nodes.append(
            GraphNode(
                id=trace_id,
                label=f"R{trace.round_index}: {trace.decision}",
                type="decision",
                detail=" / ".join(trace.decision_basis[:2]),
                data={"confidence": trace.confidence, "world_id": trace.world_id},
            )
        )
        edges.append(GraphEdge(source=trace.world_id, target=trace_id, label="decides"))

    return StoryMap(nodes=nodes, edges=edges)


def slug_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}-{digest}"
