from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import os

from ax_tree import AxNode, prune_ax_tree


AX_ERROR_SUCCESS = 0


def _load_frameworks() -> tuple[Any, Any] | None:
    try:
        import ApplicationServices as AS  # type: ignore
        import AppKit  # type: ignore
    except Exception:
        return None
    return AS, AppKit


@dataclass
class NativeObservation:
    payload: dict[str, Any]
    handles: dict[str, Any]


class MacOSAxAdapter:
    def __init__(self) -> None:
        frameworks = _load_frameworks()
        if frameworks is None:
            raise RuntimeError(
                "PyObjC frameworks are not installed. Install pyobjc-framework-ApplicationServices and pyobjc-framework-Cocoa."
            )
        self.AS, self.AppKit = frameworks

    def is_trusted(self) -> bool:
        fn = getattr(self.AS, "AXIsProcessTrusted", None)
        if fn is None:
            return True
        return bool(fn())

    def frontmost_app(self) -> Any:
        workspace = self.AppKit.NSWorkspace.sharedWorkspace()
        app = workspace.frontmostApplication()
        if app is None:
            raise RuntimeError("No frontmost application found")
        return app

    def observe_frontmost(self, max_nodes: int = 450, max_depth: int = 12) -> NativeObservation:
        if not self.is_trusted():
            raise PermissionError(
                "Accessibility permission is not granted. Enable it in System Settings > Privacy & Security > Accessibility."
            )

        app = self.frontmost_app()
        pid = int(app.processIdentifier())
        bundle_id = str(app.bundleIdentifier() or "")
        app_name = str(app.localizedName() or bundle_id or f"pid:{pid}")

        app_element = self.AS.AXUIElementCreateApplication(pid)
        window_element = self._copy_attr(app_element, "AXFocusedWindow") or app_element
        root = self._build_node(window_element, max_depth=max_depth)
        if root.title is None:
            root.title = app_name

        viewport = self._main_viewport()
        tree, elements = prune_ax_tree(
            root,
            viewport,
            app_bundle_id=bundle_id,
            window_title=root.title or app_name,
            max_nodes=max_nodes,
        )

        handles = {element_id: node.native_handle for element_id, node in elements.items() if node.native_handle is not None}
        payload = {
            "observation_id": f"obs_{os.getpid()}_{id(root)}",
            "source": "ax_native",
            "active_app": app_name,
            "active_bundle_id": bundle_id,
            "active_window": root.title or app_name,
            "screen": self._screen_payload(),
            "tree": tree.to_model_dict(),
            "elements": {key: node.to_model_dict() for key, node in elements.items()},
            "fallback_recommended": len(elements) == 0,
        }
        return NativeObservation(payload=payload, handles=handles)

    def perform_press(self, element: Any) -> tuple[bool, str]:
        err = self.AS.AXUIElementPerformAction(element, "AXPress")
        if err == AX_ERROR_SUCCESS:
            return True, "AXPress performed"
        return False, f"AXPress failed with error {err}"

    def set_value(self, element: Any, text: str) -> tuple[bool, str]:
        err = self.AS.AXUIElementSetAttributeValue(element, "AXValue", text)
        if err == AX_ERROR_SUCCESS:
            return True, "AXValue set"
        return False, f"AXValue write failed with error {err}"

    def focus(self, element: Any) -> tuple[bool, str]:
        err = self.AS.AXUIElementSetAttributeValue(element, "AXFocused", True)
        if err == AX_ERROR_SUCCESS:
            return True, "AXFocused set"
        return False, f"AXFocused write failed with error {err}"

    def _build_node(self, element: Any, *, max_depth: int, depth: int = 0) -> AxNode:
        role = self._copy_attr(element, "AXRole") or "AXUnknown"
        node = AxNode(
            role=str(role),
            title=self._string_attr(element, "AXTitle"),
            value=self._string_attr(element, "AXValue"),
            description=self._string_attr(element, "AXDescription"),
            identifier=self._string_attr(element, "AXIdentifier"),
            enabled=self._bool_attr(element, "AXEnabled", default=True),
            hidden=self._bool_attr(element, "AXHidden", default=False),
            bbox=self._bbox(element),
            actions=self._actions(element),
            native_handle=element,
        )

        if depth >= max_depth:
            return node

        children = self._copy_attr(element, "AXVisibleChildren")
        if children is None:
            children = self._copy_attr(element, "AXChildren")
        if not isinstance(children, (list, tuple)):
            return node

        for child in children:
            try:
                node.children.append(self._build_node(child, max_depth=max_depth, depth=depth + 1))
            except Exception:
                continue
        return node

    def _copy_attr(self, element: Any, attr: str) -> Any | None:
        try:
            result = self.AS.AXUIElementCopyAttributeValue(element, attr, None)
        except TypeError:
            try:
                result = self.AS.AXUIElementCopyAttributeValue(element, attr)
            except Exception:
                return None
        except Exception:
            return None

        if isinstance(result, tuple):
            if len(result) == 2:
                err, value = result
                return value if err == AX_ERROR_SUCCESS else None
            if len(result) >= 1:
                return result[-1]
        return result

    def _actions(self, element: Any) -> list[str]:
        try:
            result = self.AS.AXUIElementCopyActionNames(element, None)
        except TypeError:
            try:
                result = self.AS.AXUIElementCopyActionNames(element)
            except Exception:
                return []
        except Exception:
            return []

        if isinstance(result, tuple) and len(result) == 2:
            err, value = result
            if err != AX_ERROR_SUCCESS:
                return []
            result = value
        if isinstance(result, (list, tuple)):
            return [str(item) for item in result]
        return []

    def _string_attr(self, element: Any, attr: str) -> str | None:
        value = self._copy_attr(element, attr)
        if value is None:
            return None
        if isinstance(value, (list, tuple, dict)):
            return None
        text = str(value)
        return text if text else None

    def _bool_attr(self, element: Any, attr: str, *, default: bool) -> bool:
        value = self._copy_attr(element, attr)
        if value is None:
            return default
        return bool(value)

    def _bbox(self, element: Any) -> tuple[float, float, float, float] | None:
        position = self._copy_attr(element, "AXPosition")
        size = self._copy_attr(element, "AXSize")
        point = self._coerce_point(position)
        dims = self._coerce_size(size)
        if point is None or dims is None:
            return None
        return (point[0], point[1], dims[0], dims[1])

    def _coerce_point(self, value: Any) -> tuple[float, float] | None:
        if value is None:
            return None
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return float(value[0]), float(value[1])
        try:
            ok, out = self.AS.AXValueGetValue(value, self.AS.kAXValueCGPointType, None)
            if ok and isinstance(out, (list, tuple)) and len(out) >= 2:
                return float(out[0]), float(out[1])
        except Exception:
            pass
        try:
            return float(value.x), float(value.y)
        except Exception:
            return None

    def _coerce_size(self, value: Any) -> tuple[float, float] | None:
        if value is None:
            return None
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return float(value[0]), float(value[1])
        try:
            ok, out = self.AS.AXValueGetValue(value, self.AS.kAXValueCGSizeType, None)
            if ok and isinstance(out, (list, tuple)) and len(out) >= 2:
                return float(out[0]), float(out[1])
        except Exception:
            pass
        try:
            return float(value.width), float(value.height)
        except Exception:
            return None

    def _main_viewport(self) -> tuple[float, float, float, float]:
        screen = self.AppKit.NSScreen.mainScreen()
        if screen is None:
            return (0, 0, 1440, 900)
        frame = screen.frame()
        return (float(frame.origin.x), float(frame.origin.y), float(frame.size.width), float(frame.size.height))

    def _screen_payload(self) -> dict[str, Any]:
        screen = self.AppKit.NSScreen.mainScreen()
        if screen is None:
            return {"width": 1440, "height": 900, "scale": 1, "display_id": "main"}
        frame = screen.frame()
        return {
            "width": int(frame.size.width),
            "height": int(frame.size.height),
            "scale": float(screen.backingScaleFactor()),
            "display_id": "main",
        }
