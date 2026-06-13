# Future Stone Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable Future Stone vertical slice.

**Architecture:** Flask backend writes simulation artifacts. Vue/D3 frontend submits requests and renders story map, event stream, skill runs, and report. Runner is replay-first with PiAgent boundary preserved in schema.

**Tech Stack:** Python 3.11, Flask, Pydantic, Vue 3, Vite, D3.

---

### Task 1: Backend RED/GREEN

- [x] Write failing tests for simulation loop and API.
- [x] Verify tests fail because `app` module does not exist.
- [x] Implement schemas, repository, simulation loop, use cases, Flask routes.
- [x] Run `uv run --extra dev pytest -q`.

### Task 2: Frontend

- [x] Create Vite Vue app.
- [x] Add scenario form, five-step chain, D3 force graph, event stream, skill run list, report panel.
- [x] Run `pnpm build:web`.

### Task 3: Docs and Verification

- [x] Add README, architecture, development, constitution, design, requirements, ADR, memory bank.
- [x] Run `pnpm verify`.
- [x] Start backend and frontend.
- [x] Browser smoke test local UI.
