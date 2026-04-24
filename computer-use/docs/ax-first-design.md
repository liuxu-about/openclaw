# AX First Computer Use Design

## Goal

Build a model agnostic Computer Use layer for OpenClaw that can operate macOS applications with low latency and high stability.

## Architecture

```text
OpenClaw agent
  calls typed tools

computer-use plugin
  registers observe, act, stop, and high level computer_use tools
  enforces policy, approvals, and audit logging

local computer node
  exposes JSON-RPC over stdio or localhost
  reads AX Tree
  executes element level AX actions
  falls back to screenshot and coordinate actions only when required
```

## Perception strategy

The primary observation channel is macOS Accessibility Tree. The node reads the active application or the requested target application, converts the native accessibility hierarchy into a compact tree, and returns only visible, useful, and actionable nodes.

Vision fallback is triggered when:

- the AX Tree has too few nodes
- no interactive elements are visible
- the active window is a Canvas, WebView, or self drawn region
- repeated actions do not change the UI
- the model reports that the target element is missing
- AX API errors are frequent

## Action strategy

Prefer element level actions:

```json
{ "type": "press", "id": "btn_3" }
{ "type": "set_value", "id": "txt_2", "text": "hello" }
{ "type": "scroll", "id": "list_1", "direction": "down" }
```

Use coordinate actions only in vision fallback mode:

```json
{ "type": "vision_click", "x": 512, "y": 320, "reason": "AX tree exposes only a canvas" }
```

## Observation schema

```json
{
  "observation_id": "obs_...",
  "source": "ax",
  "active_app": "Safari",
  "active_window": "OpenClaw Docs",
  "screen": {
    "width": 1440,
    "height": 900,
    "scale": 2,
    "display_id": "main"
  },
  "tree": {
    "role": "AXWindow",
    "title": "OpenClaw Docs",
    "children": []
  },
  "elements": {
    "btn_1": {
      "role": "AXButton",
      "title": "Search",
      "bbox": [742, 88, 96, 32],
      "actions": ["AXPress"]
    }
  },
  "fallback_recommended": false
}
```

## Safety model

The plugin treats visible app content as untrusted input. It must never allow a webpage, email, chat, document, or screenshot to change system policy.

Default blocked targets:

- terminals and shells
- password managers
- banking or wallet apps
- system settings and security prompts
- OpenClaw itself

Approval is required for:

- sending messages or emails
- submitting forms that affect accounts, billing, privacy, security, production systems, or external users
- deleting or overwriting files
- entering secrets, passwords, recovery codes, tokens, or payment details
- installing software
- changing system settings

## MVP milestones

### Week 1

- Python prototype node
- AX Tree adapter interface
- pruning and element ID generation
- element level press, set_value, focus, scroll, and key action stubs
- Calculator, Safari, Finder smoke tasks

### Week 2

- OpenClaw plugin registration
- Skill file
- local node lifecycle
- allowlist and blocklist policy
- audit log

### Week 3

- ScreenCaptureKit or screenshot fallback
- vision_click action
- sensitive action approval
- Electron and WebView detection
- UI diff based verification
