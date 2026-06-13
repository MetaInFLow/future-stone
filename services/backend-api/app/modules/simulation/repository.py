from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .schemas import Progress, SimulationRequest


def runtime_root() -> Path:
    return Path(os.getenv("FUTURE_STONE_RUNTIME_DIR", "runtime/simulations"))


def simulation_dir(simulation_id: str) -> Path:
    return runtime_root() / simulation_id


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(payload, "model_dump"):
        data = payload.model_dump(mode="json")
    else:
        data = payload
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, records: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for record in records:
        if hasattr(record, "model_dump"):
            payload = record.model_dump(mode="json")
        else:
            payload = record
        lines.append(json.dumps(payload, ensure_ascii=False))
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def save_request(simulation_id: str, request: SimulationRequest) -> None:
    folder = simulation_dir(simulation_id)
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "simulation_request.json", request)
    write_json(folder / "progress.json", Progress(status="created", total_steps=0))


def load_request(simulation_id: str) -> SimulationRequest:
    return SimulationRequest.model_validate(
        read_json(simulation_dir(simulation_id) / "simulation_request.json")
    )
