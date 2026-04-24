from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ActionResult:
    ok: bool
    action: dict[str, Any]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "action": self.action, "message": self.message}


class ActionExecutor:
    """Element level action executor.

    This first version is intentionally a stub. The production implementation should
    keep a mapping from model-facing element IDs to native AXUIElement handles and
    execute actions through AXUIElementPerformAction or AXUIElementSetAttributeValue.
    """

    def __init__(self) -> None:
        self.last_actions: list[dict[str, Any]] = []

    def execute(self, actions: list[dict[str, Any]]) -> list[ActionResult]:
        results: list[ActionResult] = []
        for action in actions:
            action_type = action.get("type")
            if action_type in {"press", "focus", "set_value", "append_text", "select", "scroll", "key", "wait"}:
                self.last_actions.append(action)
                results.append(ActionResult(True, action, "accepted by prototype executor"))
                continue

            if action_type == "vision_click":
                self.last_actions.append(action)
                results.append(ActionResult(True, action, "accepted by prototype vision fallback executor"))
                continue

            results.append(ActionResult(False, action, f"unsupported action type: {action_type}"))

        return results


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
