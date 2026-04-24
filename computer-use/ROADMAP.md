# Computer Use Roadmap

## Summary

This roadmap tracks the AX-first Computer Use implementation for OpenClaw.

The initial scaffold contains:

- `README.md`: project overview
- `config.example.json`: safety and observation defaults
- `docs/ax-first-design.md`: architecture and MVP plan
- `plugin/index.ts`: TypeScript tool wrapper prototype
- `skill/SKILL.md`: model-facing usage guidance
- `node/ax_tree.py`: AX Tree pruning prototype
- `node/actions.py`: action executor and approval stub
- `node/server.py`: JSON-RPC prototype node
- `node/requirements.txt`: Python dependency notes

## Target architecture

```text
OpenClaw agent
  -> computer-use plugin tools
  -> local macOS computer node
  -> AX Tree observe/action loop
  -> optional vision fallback
```

## Phase 1: AX loop

- [ ] Replace demo AX tree with real macOS AXUIElement reading.
- [ ] Map model-facing element IDs to native AX handles.
- [ ] Implement `press` through AX actions.
- [ ] Implement `set_value` through AX value writes.
- [ ] Implement `focus`, `scroll`, `key`, and `wait`.
- [ ] Add UI diff verification after each action.

## Phase 2: OpenClaw integration

- [ ] Wire `computer-use/plugin/index.ts` to the real OpenClaw plugin SDK.
- [ ] Launch and manage the local computer node from OpenClaw.
- [ ] Add Gateway/node capability declaration.
- [ ] Install `skill/SKILL.md` into the expected skills path.
- [ ] Add config schema for `computer.*`.

## Phase 3: safety and fallback

- [ ] Enforce app allowlist and blocklist.
- [ ] Add sensitive action approval UI.
- [ ] Add audit logging.
- [ ] Add screenshot fallback.
- [ ] Add Electron, WebView, and Canvas detection.
- [ ] Implement coordinate actions only for vision fallback.

## Safety defaults

- AX Tree first.
- Screenshot only on demand.
- Element ID actions preferred.
- Coordinate actions only in fallback mode.
- Terminal, shells, password managers, system settings, wallets, banking apps, and OpenClaw itself are blocked by default.
