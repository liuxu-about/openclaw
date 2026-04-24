from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
import time


@dataclass
class ActionResult:
    ok: bool
    action: dict[str, Any]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "action": self.action, "message": self.message}


class NativeAxActions(Protocol):
    def perform_press(self, element: Any) -> tuple[bool, str]: ...

    def set_value(self, element: Any, text: str) -> tuple[bool, str]: ...

    def focus(self, element: Any) -> tuple[bool, str]: ...


class ActionExecutor:
    """Element level action executor.

    The executor receives model-facing actions and resolves element IDs against the
    most recent observation handle map. When a native AX adapter is available, it
    executes through AXUIElement operations. Otherwise it accepts actions in demo mode
    so the JSON-RPC and agent loop can be developed without macOS permissions.
    """

    def __init__(self, native_actions: NativeAxActions | None = None) -> None:
        self.native_actions = native_actions
        self.last_actions: list[dict[str, Any]] = []

    def execute(self, actions: list[dict[str, Any]], handles: dict[str, Any] | None = None) -> list[ActionResult]:
        handles = handles or {}
        results: list[ActionResult] = []
        for action in actions:
            action_type = action.get("type")
            self.last_actions.append(action)

            if action_type == "press":
                results.append(self._press(action, handles))
                continue

            if action_type == "focus":
                results.append(self._focus(action, handles))
                continue

            if action_type == "set_value":
                results.append(self._set_value(action, handles))
                continue

            if action_type == "append_text":
                results.append(self._append_text(action, handles))
                continue

            if action_type == "wait":
                ms = int(action.get("ms") or 0)
                time.sleep(max(0, min(ms, 5000)) / 1000)
                results.append(ActionResult(True, action, f"waited {ms}ms"))
                continue

            if action_type in {"select", "scroll", "key"}:
                results.append(ActionResult(True, action, "accepted by prototype executor, native fallback pending"))
                continue

            if action_type == "vision_click":
                results.append(ActionResult(True, action, "accepted by prototype vision fallback executor"))
                continue

            results.append(ActionResult(False, action, f"unsupported action type: {action_type}"))

        return results

    def _resolve(self, action: dict[str, Any], handles: dict[str, Any]) -> tuple[Any | None, ActionResult | None]:
        element_id = action.get("id")
        if not isinstance(element_id, str) or not element_id:
            return None, ActionResult(False, action, "action requires a non-empty element id")
        element = handles.get(element_id)
        if element is None:
            if self.native_actions is None:
                return None, None
            return None, ActionResult(False, action, f"element id not found in latest observation: {element_id}")
        return element, None

    def _press(self, action: dict[str, Any], handles: dict[str, Any]) -> ActionResult:
        element, error = self._resolve(action, handles)
        if error:
            return error
        if self.native_actions is None or element is None:
            return ActionResult(True, action, "accepted press in demo mode")
        ok, message = self.native_actions.perform_press(element)
        return ActionResult(ok, action, message)

    def _focus(self, action: dict[str, Any], handles: dict[str, Any]) -> ActionResult:
        element, error = self._resolve(action, handles)
        if error:
            return error
        if self.native_actions is None or element is None:
            return ActionResult(True, action, "accepted focus in demo mode")
        ok, message = self.native_actions.focus(element)
        return ActionResult(ok, action, message)

    def _set_value(self, action: dict[str, Any], handles: dict[str, Any]) -> ActionResult:
        element, error = self._resolve(action, handles)
        if error:
            return error
        text = str(action.get("text") or "")
        if self.native_actions is None or element is None:
            return ActionResult(True, action, "accepted set_value in demo mode")
        ok, message = self.native_actions.set_value(element, text)
        return ActionResult(ok, action, message)

    def _append_text(self, action: dict[str, Any], handles: dict[str, Any]) -> ActionResult:
        element, error = self._resolve(action, handles)
        if error:
            return error
        text = str(action.get("text") or "")
        if self.native_actions is None or element is None:
            return ActionResult(True, action, "accepted append_text in demo mode")
        ok, message = self.native_actions.set_value(element, text)
        return ActionResult(ok, action, message)


def action_requires_approval(action: dict[str, Any]) -> tuple[bool, str | None]:
    action_type = action.get("type")
    text = str(action.get("text") or "").lower()
    reason = str(action.get("reason") or "").lower()

    sensitive_words = [
        "password",
        "token",
        "secret",
        "recovery code",
        "payment",
        "purchase",
        "send email",
        "send message",
        "delete",
        "overwrite",
        "install",
        "system settings",
    ]

    if action_type == "vision_click" and any(word in reason for word in sensitive_words):
        return True, "vision fallback action describes a sensitive operation"

    if action_type in {"set_value", "append_text"} and any(word in text for word in sensitive_words):
        return True, "text input appears to include sensitive content"

    return False, None
