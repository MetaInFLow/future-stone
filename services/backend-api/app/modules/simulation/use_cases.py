from __future__ import annotations

import uuid
from pathlib import Path
from threading import Lock, Thread

from .repository import (
    load_request,
    read_json,
    read_jsonl,
    runtime_root,
    save_request,
    simulation_dir,
    write_json,
)
from .schemas import Progress, SimulationRequest
from .simulation_loop import run_simulation

_RUNNING_LOCK = Lock()
_RUNNING_THREADS: dict[str, Thread] = {}


def create_simulation(request: SimulationRequest) -> dict:
    simulation_id = f"sim-{uuid.uuid4().hex[:12]}"
    save_request(simulation_id, request)
    return {
        "simulation_id": simulation_id,
        "status": "created",
        "artifact_dir": str(simulation_dir(simulation_id)),
    }


def list_simulations(limit: int = 20) -> dict:
    root = runtime_root()
    if not root.exists():
        return {"simulations": []}

    folders = [path for path in root.iterdir() if path.is_dir() and path.name.startswith("sim-")]
    folders.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    simulations = []
    for folder in folders[:limit]:
        progress_path = folder / "progress.json"
        request_path = folder / "simulation_request.json"
        report_path = folder / "report.json"
        progress = read_json(progress_path) if progress_path.exists() else Progress().model_dump()
        request_payload = read_json(request_path) if request_path.exists() else {}
        report = read_json(report_path) if report_path.exists() else {}
        simulations.append(
            {
                "simulation_id": folder.name,
                "status": progress.get("status", "created"),
                "completed_steps": progress.get("completed_steps", 0),
                "total_steps": progress.get("total_steps", 0),
                "current_step": progress.get("current_step", ""),
                "updated_at": progress.get("updated_at", ""),
                "question": request_payload.get("question", ""),
                "runner": request_payload.get("runner", ""),
                "recommended_path": report.get("recommended_path", ""),
                "timeline_count": report.get("timeline_count", 0),
            }
        )
    return {"simulations": simulations}


def start_simulation(simulation_id: str) -> dict:
    request = load_request(simulation_id)
    folder = simulation_dir(simulation_id)
    if request.runner in {"llm", "piagent"}:
        return start_background_simulation(simulation_id, request, folder)

    result = run_simulation(request, output_dir=folder)
    return {
        "simulation_id": simulation_id,
        "progress": result.progress.model_dump(mode="json"),
        "report": result.report.model_dump(mode="json"),
        "story_map": result.story_map.model_dump(mode="json"),
    }


def start_background_simulation(
    simulation_id: str, request: SimulationRequest, folder: Path
) -> dict:
    if (folder / "report.json").exists() and (folder / "story_map.json").exists():
        return simulation_payload(simulation_id)

    with _RUNNING_LOCK:
        thread = _RUNNING_THREADS.get(simulation_id)
        if thread and thread.is_alive():
            return simulation_payload(simulation_id)

        progress = Progress(
            status="running",
            completed_steps=0,
            total_steps=request.world_count * request.rounds,
            current_step="queued",
            generation_source="pending",
            skill_runner_source=request.runner,
        )
        write_json(folder / "progress.json", progress)
        thread = Thread(
            target=run_background_loop,
            args=(simulation_id, request, folder),
            daemon=True,
        )
        _RUNNING_THREADS[simulation_id] = thread
        thread.start()
        return simulation_payload(simulation_id)


def run_background_loop(simulation_id: str, request: SimulationRequest, folder: Path) -> None:
    try:
        run_simulation(request, output_dir=folder)
    except Exception as exc:  # noqa: BLE001 - persist failure for the UI instead of losing it.
        write_json(
            folder / "progress.json",
            Progress(
                status="failed",
                current_step=str(exc),
                total_steps=request.world_count * request.rounds,
            ),
        )
    finally:
        with _RUNNING_LOCK:
            _RUNNING_THREADS.pop(simulation_id, None)


def simulation_payload(simulation_id: str) -> dict:
    folder = simulation_dir(simulation_id)
    report_path = folder / "report.json"
    story_map_path = folder / "story_map.json"
    return {
        "simulation_id": simulation_id,
        "progress": get_status(simulation_id),
        "report": read_json(report_path) if report_path.exists() else None,
        "story_map": read_json(story_map_path) if story_map_path.exists() else None,
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
