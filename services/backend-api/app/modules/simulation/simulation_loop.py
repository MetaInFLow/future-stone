from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

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

SELF_LENSES = [
    ("current-self", "当前的我", "按现有惯性做选择"),
    ("long-term-self", "长期主义的我", "从 3 年和 10 年后回看"),
    ("reality-self", "现实约束的我", "检查现金流、时间、资源和团队状态"),
    ("brave-self", "更勇敢的我", "去掉恐惧后的选择"),
    ("contrarian-self", "反方的我", "识别幻觉、自嗨和过度叙事"),
    ("mission-observer", "使命观察者", "判断是否靠近我是谁"),
]

WORLD_PATTERNS = [
    ("赛题高度贴合 LifeOS", ["评委关注真实 demo", "现场资源密集", "传播机会强"], "使命与窗口"),
    ("赛题偏离主线", ["题目偏工具化", "demo 难以沉淀", "时间被切碎"], "方向偏离"),
    ("团队状态紧张", ["睡眠不足", "分工不稳", "外部承诺挤压"], "资源约束"),
    ("NPC 强烈支持", ["参赛者愿意共创", "评委期待叙事", "家人接受短期投入"], "关系助推"),
    ("外部反馈冷淡", ["用户不理解", "评委只看功能", "传播噪音高"], "市场误读"),
]


def run_simulation(request: SimulationRequest, output_dir: Path) -> SimulationResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    scenario_graph = build_scenario_graph(request)
    worlds = build_worlds(request)
    npcs = build_npcs(worlds, request.npc_roles)
    progress = Progress(
        status="running",
        completed_steps=0,
        total_steps=len(worlds) * request.rounds,
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

            skill_run, trace = run_replay_skill(world, round_index, round_events, request)
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


def build_worlds(request: SimulationRequest) -> list[World]:
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


def build_npcs(worlds: list[World], roles: list[str]) -> list[Npc]:
    npcs = []
    for world in worlds:
        for index, role in enumerate(roles, start=1):
            influence = 1 + stable_int(f"{world.id}:{role}", 5)
            stance = stance_for(role, world.dominant_tension, influence)
            npcs.append(
                Npc(
                    id=f"{world.id}-npc-{index}",
                    world_id=world.id,
                    role=role,
                    name=f"{role}-{world.id[-3:]}",
                    stance=stance,
                    influence=influence,
                    goal=goal_for(role),
                )
            )
    return npcs


def build_event(
    world: World, npc: Npc, round_index: int, request: SimulationRequest
) -> SimulationEvent:
    message = (
        f"在{world.title}第 {round_index} 轮，{npc.role}从“{world.dominant_tension}”角度施压："
        f"{npc.stance}。"
    )
    response = (
        f"Avatar 先承认 {npc.role} 的约束，再把问题拉回 {request.question} "
        f"和 LifeOS 主线是否一致。"
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
            "lifeos://self-model/decision-factors",
            "lifeos://principle/human-decides-ai-simulates",
        ],
    )


def run_replay_skill(
    world: World,
    round_index: int,
    events: list[SimulationEvent],
    request: SimulationRequest,
) -> tuple[SkillRun, DecisionTrace]:
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

    skill_ref = "lifeos://skill/decision-simulation/replay"
    rationale = (
        f"{world.title} 的主张是 {decision}。依据是外部变量、NPC 压力、"
        "长期主义视角和现实约束共同评分。"
    )
    confidence = max(0.35, min(0.92, 0.58 + score / 30))
    skill_run = SkillRun(
        id=f"{world.id}-round-{round_index}-skill-run",
        world_id=world.id,
        round_index=round_index,
        skill_ref=skill_ref,
        runner=request.runner,
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
        decision_basis=[
            f"外部变量：{', '.join(world.external_variables)}",
            f"世界张力：{world.dominant_tension}",
            "当前的我：偏向把高密度事件转成可展示产物",
            "长期主义的我：只接受能沉淀 LifeOS 主线资产的投入",
            "反方的我：警惕为了比赛而比赛、为了叙事而牺牲 M1",
        ],
        npc_effects=[f"{event.npc_role}: {event.impact:+d}" for event in events],
        self_model_refs=[
            "lifeos://avatar/decision-factors",
            "lifeos://avatar/boundary/human-decides",
        ],
        confidence=skill_run.confidence,
    )
    return skill_run, trace


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
