"""In-process mock lab engine for local topology simulation without Eve-NG."""

from __future__ import annotations

import uuid
from typing import Any

from app.services.lab.base import (
    LabEngine,
    LabLinkSpec,
    LabNodeSpec,
    LabStatusResult,
    LabSyncResult,
)


class MockLabEngine(LabEngine):
    """Stores lab state in memory so sync/start/stop work without an Eve-NG server."""

    name = "mock"

    def __init__(self) -> None:
        self._labs: dict[str, dict[str, Any]] = {}

    def is_configured(self) -> bool:
        return True

    async def sync_lab(
        self,
        *,
        lab_name: str,
        existing_path: str | None,
        nodes: list[LabNodeSpec],
        links: list[LabLinkSpec],
        existing_node_map: dict[str, str] | None = None,
    ) -> LabSyncResult:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in lab_name) or "lab"
        lab_path = existing_path or f"/mock/labs/{safe}.unl"
        node_map = dict(existing_node_map or {})
        for spec in nodes:
            if spec.local_id not in node_map:
                node_map[spec.local_id] = f"mock-{uuid.uuid4().hex[:8]}"
        # Drop mappings for removed nodes
        keep = {n.local_id for n in nodes}
        node_map = {k: v for k, v in node_map.items() if k in keep}

        self._labs[lab_path] = {
            "name": lab_name,
            "nodes": {n.local_id: n for n in nodes},
            "links": links,
            "node_map": node_map,
            "running": set(),
        }
        return LabSyncResult(
            lab_path=lab_path,
            node_map=node_map,
            message=f"已同步到本地模拟实验室（{len(nodes)} 节点 / {len(links)} 链路）",
        )

    async def start_lab(self, lab_path: str, node_map: dict[str, str]) -> LabStatusResult:
        lab = self._labs.setdefault(
            lab_path,
            {"name": lab_path, "nodes": {}, "links": [], "node_map": node_map, "running": set()},
        )
        lab["node_map"] = dict(node_map)
        lab["running"] = set(node_map.keys())
        status = {lid: "running" for lid in node_map}
        return LabStatusResult(status="running", node_status=status, message="本地模拟实验室已启动")

    async def stop_lab(self, lab_path: str, node_map: dict[str, str]) -> LabStatusResult:
        lab = self._labs.get(lab_path)
        if lab is not None:
            lab["running"] = set()
        status = {lid: "stopped" for lid in node_map}
        return LabStatusResult(status="stopped", node_status=status, message="本地模拟实验室已停止")

    async def get_status(self, lab_path: str, node_map: dict[str, str]) -> LabStatusResult:
        lab = self._labs.get(lab_path)
        running = set(lab.get("running") or []) if lab else set()
        status = {
            lid: ("running" if lid in running else "stopped") for lid in node_map
        }
        overall = "running" if running else ("synced" if node_map else "idle")
        return LabStatusResult(status=overall, node_status=status)

    async def console_url(self, lab_path: str, external_node_id: str) -> str | None:
        # No real console; frontend can show the message from API
        return f"mock://console/{external_node_id}"
