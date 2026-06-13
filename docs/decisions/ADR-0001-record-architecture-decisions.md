# ADR-0001 Record Architecture Decisions

- Status: accepted
- Date: 2026-06-13

## Decision

Future Stone 使用 Flask + Vue + D3 的 Web + Backend 结构，artifact 先落本地 JSON/JSONL。

## Reason

MiroFish 的可借鉴价值在五步链路和可视化，而不是 OASIS runner。Flask + Vue + D3 能最大化复用这种产品形态，同时保持代码独立。

## Consequence

PiAgent 接入被隔离在 runner 层。前端只依赖稳定 artifact schema。

