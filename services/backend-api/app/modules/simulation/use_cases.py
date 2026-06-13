from __future__ import annotations

import uuid
from pathlib import Path

from .repository import (
    load_request,
    read_json,
    read_jsonl,
    save_request,
    simulation_dir,
)
from .schemas import Progress, SimulationRequest
from .simulation_loop import run_simulation


def create_simulation(request: SimulationRequest) -> dict:
    simulation_id = f"sim-{uuid.uuid4().hex[:12]}"
    save_request(simulation_id, request)
    return {
        "simulation_id": simulation_id,
        "status": "created",
        "artifact_dir": str(simulation_dir(simulation_id)),
    }


def start_simulation(simulation_id: str) -> dict:
    request = load_request(simulation_id)
    folder = simulation_dir(simulation_id)
    result = run_simulation(request, output_dir=folder)
    return {
        "simulation_id": simulation_id,
        "progress": result.progress.model_dump(mode="json"),
        "report": result.report.model_dump(mode="json"),
        "story_map": result.story_map.model_dump(mode="json"),
    }


def get_status(simulation_id: str) -> dict:
    progress_path = simulation_dir(simulation_id) / "progress.json"
    if not progress_path.exists():
        return Progress(status="created").model_dump(mode="json")
    return read_json(progress_path)


def get_story_map(simulation_id: str) -> dict:
    return read_json(required_path(simulation_id, "story_map.json"))


def get_report(simulation_id: str) -> dict:
    return read_json(required_path(simulation_id, "report.json"))


def get_events(simulation_id: str) -> list[dict]:
    return read_jsonl(required_path(simulation_id, "simulation_events.jsonl"))


def get_skill_runs(simulation_id: str) -> list[dict]:
    return read_jsonl(required_path(simulation_id, "skill_runs.jsonl"))


def get_decision_traces(simulation_id: str) -> list[dict]:
    return read_jsonl(required_path(simulation_id, "decision_traces.jsonl"))


def required_path(simulation_id: str, file_name: str) -> Path:
    path = simulation_dir(simulation_id) / file_name
    if not path.exists():
        raise FileNotFoundError(f"Simulation artifact not found: {path}")
    return path

