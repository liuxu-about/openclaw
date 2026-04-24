from __future__ import annotations

import json
import sys
from typing import Any

from actions import ActionExecutor, action_requires_approval
from ax_tree import observe_demo

try:
    from ax_macos import MacOSAxAdapter
except Exception:
    MacOSAxAdapter = None  # type: ignore


class ComputerNodeState:
    def __init__(self) -> None:
        self.native_adapter: Any | None = None
        self.native_error: str | None = None
        self.last_handles: dict[str, Any] = {}
        self.last_observation: dict[str, Any] | None = None
        self.executor = ActionExecutor()
        self._init_native_adapter()

    def _init_native_adapter(self) -> None:
        if MacOSAxAdapter is None:
            self.native_error = "native macOS AX adapter module is not available"
            return
        try:
            self.native_adapter = MacOSAxAdapter()
            self.executor = ActionExecutor(native_actions=self.native_adapter)
        except Exception as exc:
            self.native_error = str(exc)
            self.native_adapter = None
            self.executor = ActionExecutor()

    def observe(self, max_nodes: int) -> dict[str, Any]:
        if self.native_adapter is not None:
            try:
                observation = self.native_adapter.observe_frontmost(max_nodes=max_nodes)
                self.last_handles = observation.handles
                self.last_observation = observation.payload
                return observation.payload
            except Exception as exc:
                self.native_error = str(exc)

        payload, handles = observe_demo(max_nodes=max_nodes)
        payload["native_unavailable_reason"] = self.native_error
        self.last_handles = handles
        self.last_observation = payload
        return payload

    def act(self, actions: list[dict[str, Any]]) -> dict[str, Any]:
        approval_reasons: list[str] = []
        for action in actions:
            required, reason = action_requires_approval(action)
            if required and reason:
                approval_reasons.append(reason)

        if approval_reasons:
            return {
                "ok": False,
                "requires_approval": True,
                "approval_reasons": approval_reasons,
                "results": [],
            }

        results = self.executor.execute(actions, handles=self.last_handles)
        return {
            "ok": all(result.ok for result in results),
            "requires_approval": False,
            "results": [result.to_dict() for result in results],
            "next_observation": self.observe(max_nodes=450),
        }

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "mode": "ax_native" if self.native_adapter is not None else "ax_demo",
            "platform": "darwin",
            "native_available": self.native_adapter is not None,
            "native_error": self.native_error,
        }


state = ComputerNodeState()


def jsonrpc_result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def jsonrpc_error(request_id: Any, code: int, message: str, data: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def handle(method: str, params: dict[str, Any]) -> Any:
    if method == "computer.observe":
        max_nodes = int(params.get("max_nodes") or 450)
        return state.observe(max_nodes=max_nodes)

    if method == "computer.act":
        actions = params.get("actions") or []
        if not isinstance(actions, list):
            raise ValueError("actions must be a list")
        for action in actions:
            if not isinstance(action, dict):
                raise ValueError("each action must be an object")
        return state.act(actions)

    if method == "computer.stop":
        return {"ok": True, "message": "prototype computer node stopped"}

    if method == "computer.health":
        return state.health()

    raise ValueError(f"unknown method: {method}")


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            request_id = request.get("id")
            method = request.get("method")
            params = request.get("params") or {}
            if not isinstance(method, str):
                response = jsonrpc_error(request_id, -32600, "method must be a string")
            elif not isinstance(params, dict):
                response = jsonrpc_error(request_id, -32600, "params must be an object")
            else:
                response = jsonrpc_result(request_id, handle(method, params))
        except Exception as exc:
            response = jsonrpc_error(None, -32000, str(exc))

        print(json.dumps(response, ensure_ascii=False), flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
