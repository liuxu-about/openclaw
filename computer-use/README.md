# OpenClaw Computer Use

This directory is an initial AX-first Computer Use prototype for OpenClaw.

The intended architecture is:

```text
OpenClaw agent
  -> computer-use plugin tools
  -> local macOS computer node
  -> Accessibility Tree observe/action loop
  -> optional vision fallback
```

## Design principles

1. AX Tree is the primary perception channel.
2. Vision is only a fallback for Canvas, Electron, WebView, images, charts, or incomplete accessibility trees.
3. Actions should target element IDs rather than raw coordinates.
4. Coordinates are only allowed in vision fallback mode.
5. Sensitive operations require user approval before execution.
6. Terminal, shells, password managers, system settings, wallets, banking apps, and OpenClaw itself are blocked by default.

## Directory layout

```text
computer-use/
├── README.md
├── config.example.json
├── docs/
│   └── ax-first-design.md
├── plugin/
│   └── index.ts
├── skill/
│   └── SKILL.md
└── node/
    ├── ax_tree.py
    ├── actions.py
    ├── server.py
    └── requirements.txt
```

## MVP scope

The first useful version should support macOS only:

- observe active app/window using Accessibility APIs
- prune AX Tree into a compact model-facing tree
- assign short element IDs like `btn_1`, `txt_2`, `menu_3`
- perform element-level actions like `press`, `set_value`, `focus`, `scroll`, and `key`
- call screenshot/vision fallback only when AX is insufficient
- record audit logs for observation/action/approval events

## Next steps

1. Run the Python prototype node locally on macOS.
2. Replace the stub AX adapter with PyObjC or a Swift helper backed by AXUIElement/AXorcist.
3. Wire the TypeScript plugin to OpenClaw's actual plugin SDK registration API.
4. Add approval UI in the Gateway/client path.
5. Add ScreenCaptureKit-based screenshot fallback.
