from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Iterable
import hashlib


INTERACTIVE_ROLES = {
    "AXButton",
    "AXCheckBox",
    "AXRadioButton",
    "AXTextField",
    "AXTextArea",
    "AXComboBox",
    "AXPopUpButton",
    "AXMenuButton",
    "AXMenuItem",
    "AXLink",
    "AXSlider",
    "AXCell",
    "AXRow",
    "AXTab",
    "AXDisclosureTriangle",
}

STRUCTURAL_ROLES = {
    "AXGroup",
    "AXLayoutArea",
    "AXLayoutItem",
    "AXSplitGroup",
    "AXScrollArea",
    "AXUnknown",
}

TEXT_ROLES = {
    "AXStaticText",
    "AXTextField",
    "AXTextArea",
}

ROLE_PREFIX = {
    "AXButton": "btn",
    "AXTextField": "txt",
    "AXTextArea": "txt",
    "AXCheckBox": "chk",
    "AXRadioButton": "rad",
    "AXLink": "lnk",
    "AXMenuItem": "menu",
    "AXRow": "row",
    "AXCell": "cell",
    "AXTab": "tab",
    "AXSlider": "sld",
}


@dataclass
class AxNode:
    role: str
    title: str | None = None
    value: str | None = None
    description: str | None = None
    identifier: str | None = None
    enabled: bool = True
    hidden: bool = False
    bbox: tuple[float, float, float, float] | None = None
    actions: list[str] = field(default_factory=list)
    children: list["AxNode"] = field(default_factory=list)
    id: str | None = None
    path: str | None = None
    stable_key: str | None = None
    native_handle: Any | None = field(default=None, repr=False, compare=False)

    def to_model_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("native_handle", None)
        return {key: value for key, value in data.items() if value not in (None, [], False)}


def intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def visible(node: AxNode, viewport: tuple[float, float, float, float]) -> bool:
    if node.hidden:
        return False
    if node.bbox is None:
        return True
    x, y, w, h = node.bbox
    if w <= 0 or h <= 0:
        return False
    return intersects(node.bbox, viewport)


def label_of(node: AxNode) -> str:
    parts = [node.title, node.value, node.description, node.identifier]
    return " ".join(str(p).strip() for p in parts if p and str(p).strip())


def useful(node: AxNode) -> bool:
    if node.role in INTERACTIVE_ROLES:
        return True
    if node.actions:
        return True
    if node.role in TEXT_ROLES and label_of(node):
        return True
    return False


def stable_hash(parts: Iterable[Any]) -> str:
    raw = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def compact_text(s: str | None, limit: int = 120) -> str | None:
    if not s:
        return None
    s = " ".join(str(s).split())
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "…"


def prune_ax_tree(
    root: AxNode,
    viewport: tuple[float, float, float, float],
    *,
    app_bundle_id: str = "",
    window_title: str = "",
    max_nodes: int = 450,
    max_children_per_list: int = 30,
) -> tuple[AxNode, dict[str, AxNode]]:
    id_counter: dict[str, int] = {}
    id_map: dict[str, AxNode] = {}

    def next_id(role: str) -> str:
        prefix = ROLE_PREFIX.get(role, "el")
        id_counter[prefix] = id_counter.get(prefix, 0) + 1
        return f"{prefix}_{id_counter[prefix]}"

    def walk(node: AxNode, path: str, depth: int = 0) -> AxNode | None:
        if len(id_map) >= max_nodes:
            return None

        if not visible(node, viewport):
            return None

        children: list[AxNode] = []
        for i, child in enumerate(node.children[:max_children_per_list]):
            child_path = f"{path}.{child.role}:{i}"
            pruned = walk(child, child_path, depth + 1)
            if pruned:
                children.append(pruned)

        node_is_useful = useful(node)

        if not node_is_useful and node.role in STRUCTURAL_ROLES:
            if len(children) == 1:
                return children[0]
            if not children:
                return None

        clean = AxNode(
            role=node.role,
            title=compact_text(node.title),
            value=compact_text(node.value),
            description=compact_text(node.description),
            identifier=compact_text(node.identifier, 80),
            enabled=node.enabled,
            hidden=False,
            bbox=node.bbox,
            actions=node.actions[:],
            children=children,
            path=path,
            native_handle=node.native_handle,
        )

        clean.stable_key = stable_hash(
            [
                app_bundle_id,
                window_title,
                clean.role,
                clean.identifier,
                clean.title,
                clean.value,
                clean.bbox,
                path,
            ]
        )

        if node_is_useful:
            clean.id = next_id(node.role)
            id_map[clean.id] = clean

        return clean

    pruned_root = walk(root, "root")
    if pruned_root is None:
        pruned_root = AxNode(role="AXApplication", title="No visible accessible content")

    return pruned_root, id_map


def build_demo_tree() -> AxNode:
    return AxNode(
        role="AXWindow",
        title="Demo Calculator",
        bbox=(0, 0, 500, 500),
        children=[
            AxNode(role="AXTextField", title="Display", value="0", bbox=(20, 20, 460, 50), actions=["AXConfirm"]),
            AxNode(role="AXButton", title="5", bbox=(20, 100, 80, 60), actions=["AXPress"]),
            AxNode(role="AXButton", title="multiply", bbox=(110, 100, 80, 60), actions=["AXPress"]),
            AxNode(role="AXButton", title="4", bbox=(200, 100, 80, 60), actions=["AXPress"]),
            AxNode(role="AXButton", title="equals", bbox=(290, 100, 80, 60), actions=["AXPress"]),
        ],
    )


def observe_demo(max_nodes: int = 450) -> tuple[dict[str, Any], dict[str, Any]]:
    viewport = (0, 0, 1440, 900)
    root, elements = prune_ax_tree(
        build_demo_tree(),
        viewport,
        app_bundle_id="demo.calculator",
        window_title="Demo Calculator",
        max_nodes=max_nodes,
    )
    payload = {
        "observation_id": "obs_demo",
        "source": "ax_demo",
        "active_app": "Demo Calculator",
        "active_window": "Demo Calculator",
        "screen": {"width": 1440, "height": 900, "scale": 2, "display_id": "main"},
        "tree": root.to_model_dict(),
        "elements": {key: node.to_model_dict() for key, node in elements.items()},
        "fallback_recommended": len(elements) == 0,
    }
    handles = {key: node.native_handle for key, node in elements.items() if node.native_handle is not None}
    return payload, handles
