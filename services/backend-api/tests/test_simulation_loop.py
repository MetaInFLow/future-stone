from app.modules.simulation.generation import ScenarioGeneration
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
        runner="replay",
    )

    result = run_simulation(request, output_dir=tmp_path)

    assert len(result.worlds) == 1
    assert result.progress.total_steps == 1
    assert len(result.decision_traces) == 1


class FakeScenarioGenerator:
    def generate(self, request):
        return ScenarioGeneration(
            source="fake-llm",
            model="test-model",
            worlds=[
                {
                    "id": "world-001",
                    "title": "真实生成的投资人突然到场时间线",
                    "summary": "模型根据场景生成，不来自固定 WORLD_PATTERNS。",
                    "external_variables": ["投资人临时出现", "评委追问真实用户", "Neil 质疑范围"],
                    "pressure_level": 5,
                    "dominant_tension": "真实机会与 M1 失焦之间的冲突",
                }
            ],
            npcs=[
                {
                    "id": "world-001-npc-1",
                    "world_id": "world-001",
                    "role": "评委",
                    "name": "追问商业化的评委",
                    "stance": "要求看到真实用户和可验证闭环",
                    "influence": 4,
                    "goal": "判断这是不是一个产品而不只是故事",
                }
            ],
        )


class FakeSkillRunner:
    source = "fake-skill-runner"
    model = "test-model"

    def run(self, world, round_index, events, request):
        return {
            "decision": "条件参加",
            "rationale": "只有把黑客松变成 Future Stone 真实 demo sprint 才参加。",
            "confidence": 0.81,
            "decision_basis": [
                "投资人临时出现会放大真实验证价值",
                "Neil 的质疑要求强制收敛范围",
                "评委追问真实用户，正好验证 LifeOS 母命题",
            ],
            "self_model_refs": ["lifeos://avatar/anthony/decision-factors"],
        }


def test_run_simulation_uses_generated_worlds_and_skill_decisions(tmp_path):
    request = SimulationRequest(
        scene=SceneInput(description="一个不是黑客松的自定义场景"),
        question="要不要改变发布策略？",
        world_count=1,
        rounds=1,
        avatars=["AnthonyFan.LifeOS"],
        npc_roles=["评委"],
        runner="llm",
    )

    result = run_simulation(
        request,
        output_dir=tmp_path,
        generator=FakeScenarioGenerator(),
        skill_runner=FakeSkillRunner(),
    )

    assert result.progress.generation_source == "fake-llm"
    assert result.progress.skill_runner_source == "fake-skill-runner"
    assert result.worlds[0].title == "真实生成的投资人突然到场时间线"
    assert result.npcs[0].name == "追问商业化的评委"
    assert result.skill_runs[0].runner == "fake-skill-runner"
    assert result.decision_traces[0].decision_basis[0] == "投资人临时出现会放大真实验证价值"
