from __future__ import annotations

from flask import Flask, jsonify, request
from flask_cors import CORS
from pydantic import ValidationError

from app.modules.simulation.schemas import SimulationRequest
from app.modules.simulation.use_cases import (
    create_simulation,
    get_decision_traces,
    get_events,
    get_report,
    get_skill_runs,
    get_status,
    get_story_map,
    start_simulation,
)


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    @app.get("/api/health")
    def health():
        return jsonify({"success": True, "data": {"status": "ok", "service": "future-stone"}})

    @app.post("/api/simulations")
    def create_simulation_route():
        try:
            payload = request.get_json(force=True)
            sim_request = SimulationRequest.model_validate(payload)
            return jsonify({"success": True, "data": create_simulation(sim_request)}), 201
        except ValidationError as exc:
            return jsonify({"success": False, "error": exc.errors()}), 400

    @app.post("/api/simulations/<simulation_id>/start")
    def start_simulation_route(simulation_id: str):
        try:
            return jsonify({"success": True, "data": start_simulation(simulation_id)})
        except FileNotFoundError as exc:
            return jsonify({"success": False, "error": str(exc)}), 404

    @app.get("/api/simulations/<simulation_id>/status")
    def get_status_route(simulation_id: str):
        return jsonify({"success": True, "data": get_status(simulation_id)})

    @app.get("/api/simulations/<simulation_id>/story-map")
    def get_story_map_route(simulation_id: str):
        try:
            return jsonify({"success": True, "data": get_story_map(simulation_id)})
        except FileNotFoundError as exc:
            return jsonify({"success": False, "error": str(exc)}), 404

    @app.get("/api/simulations/<simulation_id>/report")
    def get_report_route(simulation_id: str):
        try:
            return jsonify({"success": True, "data": get_report(simulation_id)})
        except FileNotFoundError as exc:
            return jsonify({"success": False, "error": str(exc)}), 404

    @app.get("/api/simulations/<simulation_id>/events")
    def get_events_route(simulation_id: str):
        try:
            return jsonify({"success": True, "data": {"events": get_events(simulation_id)}})
        except FileNotFoundError as exc:
            return jsonify({"success": False, "error": str(exc)}), 404

    @app.get("/api/simulations/<simulation_id>/skill-runs")
    def get_skill_runs_route(simulation_id: str):
        try:
            return jsonify({"success": True, "data": {"skill_runs": get_skill_runs(simulation_id)}})
        except FileNotFoundError as exc:
            return jsonify({"success": False, "error": str(exc)}), 404

    @app.get("/api/simulations/<simulation_id>/decision-traces")
    def get_decision_traces_route(simulation_id: str):
        try:
            return jsonify(
                {"success": True, "data": {"decision_traces": get_decision_traces(simulation_id)}}
            )
        except FileNotFoundError as exc:
            return jsonify({"success": False, "error": str(exc)}), 404

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5055, debug=True)
