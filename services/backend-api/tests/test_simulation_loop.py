from app.modules.simulation.schemas import SceneInput, SimulationRequest
from app.modules.simulation.simulation_loop import run_simulation


def test_run_simulation_produces_worlds_events_decision_traces_and_report(tmp_path):
    request = SimulationRequest(
        scene=SceneInput(
            description="要不要参加黑客松？需要考虑 LifeOS demo、团队状态、家人时间和评委反馈。",
        ),
        question="Anthony 和 Neil 是否应该参加这次黑客松？",
        world_count=3,
        rounds=2,
        avatars=["AnthonyFan.LifeOS", "Neil.LifeOS"],
        npc_roles=["参赛选手", "家人", "评委"],
        runner="replay",
    )

    result = run_simulation(request, output_dir=tmp_path)

    assert len(result.worlds) == 3
    assert len(result.npcs) == 9
    assert result.progress.status == "completed"
    assert result.progress.completed_steps == result.progress.total_steps
    assert len(result.events) == 3 * 2 * 3
    assert len(result.skill_runs) == 3 * 2
    assert len(result.decision_traces) == 3 * 2
    assert result.report.recommended_path in {"参加", "不参加", "条件参加"}
    assert result.story_map.nodes
    assert result.story_map.edges

    first_trace = result.decision_traces[0]
    assert first_trace.decision_basis
    assert first_trace.skill_ref.startswith("lifeos://skill/")
    assert first_trace.world_id == "world-001"

    expected_files = [
        "simulation_request.json",
        "scenario_graph.json",
        "worlds.json",
        "npcs.json",
        "progress.json",
        "simulation_events.jsonl",
        "skill_runs.jsonl",
        "decision_traces.jsonl",
        "report.json",
        "story_map.json",
    ]
    for file_name in expected_files:
        assert (tmp_path / file_name).exists(), file_name


def test_world_count_and_rounds_are_bounded(tmp_path):
    request = SimulationRequest(
        scene=SceneInput(description="是否要 All in LifeOS？"),
        question="现在是否应该 All in LifeOS？",
        world_count=0,
        rounds=0,
        avatars=["AnthonyFan.LifeOS"],
        npc_roles=[],
    )

    result = run_simulation(request, output_dir=tmp_path)

    assert len(result.worlds) == 1
    assert result.progress.total_steps == 1
    assert len(result.decision_traces) == 1

