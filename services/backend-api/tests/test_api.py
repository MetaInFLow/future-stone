from app.main import create_app
from app.modules.simulation import use_cases
from app.modules.simulation.repository import save_request
from app.modules.simulation.schemas import Progress, Report, SceneInput, SimulationRequest, StoryMap


def test_create_and_run_simulation_returns_report(tmp_path, monkeypatch):
    monkeypatch.setenv("FUTURE_STONE_RUNTIME_DIR", str(tmp_path))
    app = create_app()
    client = app.test_client()

    create_response = client.post(
        "/api/simulations",
        json={
            "scene": {"description": "要不要参加黑客松？"},
            "question": "是否参加黑客松？",
            "world_count": 2,
            "rounds": 2,
            "avatars": ["AnthonyFan.LifeOS", "Neil.LifeOS"],
            "npc_roles": ["参赛选手", "家人", "评委"],
            "runner": "replay",
        },
    )

    assert create_response.status_code == 201
    simulation_id = create_response.get_json()["data"]["simulation_id"]

    run_response = client.post(f"/api/simulations/{simulation_id}/start")
    assert run_response.status_code == 200
    run_data = run_response.get_json()["data"]
    assert run_data["progress"]["status"] == "completed"
    assert run_data["report"]["timeline_count"] == 2

    events_response = client.get(f"/api/simulations/{simulation_id}/events")
    assert events_response.status_code == 200
    assert events_response.get_json()["data"]["events"]


def test_llm_start_returns_running_without_waiting_for_full_loop(tmp_path, monkeypatch):
    monkeypatch.setenv("FUTURE_STONE_RUNTIME_DIR", str(tmp_path))
    simulation_id = "sim-async-test"
    request = SimulationRequest(
        scene=SceneInput(description="要不要参加黑客松？"),
        question="是否参加黑客松？",
        world_count=2,
        rounds=1,
        runner="llm",
    )
    save_request(simulation_id, request)

    import threading
    from types import SimpleNamespace

    started = threading.Event()
    release = threading.Event()

    def fake_run_simulation(request, output_dir):
        started.set()
        release.wait(timeout=2)
        return SimpleNamespace(
            progress=Progress(status="completed", completed_steps=2, total_steps=2),
            report=Report(
                title="test",
                question=request.question,
                recommended_path="条件参加",
                timeline_count=2,
                decision_distribution={"条件参加": 2},
                decisive_factors=[],
                risks=[],
                opportunities=[],
                summary="test",
            ),
            story_map=StoryMap(nodes=[], edges=[]),
        )

    monkeypatch.setattr(use_cases, "run_simulation", fake_run_simulation)

    response = use_cases.start_simulation(simulation_id)

    assert response["progress"]["status"] == "running"
    assert response["report"] is None
    assert response["story_map"] is None
    assert started.wait(timeout=1)
    release.set()


def test_list_simulations_returns_latest_report_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("FUTURE_STONE_RUNTIME_DIR", str(tmp_path))
    app = create_app()
    client = app.test_client()

    create_response = client.post(
        "/api/simulations",
        json={
            "scene": {"description": "要不要参加黑客松？"},
            "question": "是否参加黑客松？",
            "world_count": 1,
            "rounds": 1,
            "runner": "replay",
        },
    )
    simulation_id = create_response.get_json()["data"]["simulation_id"]
    client.post(f"/api/simulations/{simulation_id}/start")

    list_response = client.get("/api/simulations")

    assert list_response.status_code == 200
    simulations = list_response.get_json()["data"]["simulations"]
    assert simulations[0]["simulation_id"] == simulation_id
    assert simulations[0]["status"] == "completed"
    assert simulations[0]["recommended_path"] in {"参加", "不参加", "条件参加"}
    assert simulations[0]["timeline_count"] == 1
