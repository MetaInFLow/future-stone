from app.main import create_app


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

