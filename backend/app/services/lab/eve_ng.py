"""Eve-NG REST adapter (credentials stay server-side)."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import Settings
from app.services.lab.base import (
    LabEngine,
    LabLinkSpec,
    LabNodeSpec,
    LabStatusResult,
    LabSyncResult,
)

logger = logging.getLogger(__name__)


class EveNgAdapter(LabEngine):
    name = "eve-ng"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cookie: str | None = None

    def is_configured(self) -> bool:
        return bool(self.settings.eve_ng_base_url.strip())

    def _base(self) -> str:
        return self.settings.eve_ng_base_url.rstrip("/")

    async def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base(),
            verify=self.settings.eve_ng_verify_ssl,
            timeout=60.0,
            follow_redirects=True,
        )

    async def _login(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/auth/login",
            json={
                "username": self.settings.eve_ng_user,
                "password": self.settings.eve_ng_password,
            },
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Eve-NG 登录失败: HTTP {resp.status_code} {resp.text[:200]}")
        # Cookie jar kept by client; also stash token if returned
        data = {}
        try:
            data = resp.json()
        except Exception:
            pass
        token = (data.get("data") or {}).get("token") if isinstance(data, dict) else None
        if token:
            self._cookie = str(token)
            client.headers["Cookie"] = f"unetlab_session={token}"

    def _lab_api_path(self, lab_path: str) -> str:
        # Eve expects path like /api/labs/folder/name.unl
        path = lab_path if lab_path.startswith("/") else f"/{lab_path}"
        if not path.endswith(".unl"):
            path = f"{path}.unl"
        return f"/api/labs{quote(path, safe='/.')}"

    async def sync_lab(
        self,
        *,
        lab_name: str,
        existing_path: str | None,
        nodes: list[LabNodeSpec],
        links: list[LabLinkSpec],
        existing_node_map: dict[str, str] | None = None,
    ) -> LabSyncResult:
        if not self.is_configured():
            raise RuntimeError("未配置 EVE_NG_BASE_URL")

        root = self.settings.eve_ng_lab_path.rstrip("/")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in lab_name) or "lab"
        lab_path = existing_path or f"{root}/{safe_name}.unl"
        if not lab_path.endswith(".unl"):
            lab_path = f"{lab_path}.unl"

        node_map = dict(existing_node_map or {})

        async with await self._client() as client:
            await self._login(client)
            lab_api = self._lab_api_path(lab_path)

            # Create lab if missing
            get_lab = await client.get(lab_api)
            if get_lab.status_code == 404:
                create = await client.post(
                    "/api/labs",
                    json={
                        "path": lab_path.rsplit("/", 1)[0] + "/",
                        "name": safe_name,
                        "version": "1",
                        "author": "RackDCIM",
                        "description": lab_name,
                        "body": "",
                    },
                )
                if create.status_code >= 400:
                    # Fallback: some Eve builds want path without trailing slash nuances
                    raise RuntimeError(f"创建 Eve-NG Lab 失败: {create.text[:300]}")

            # Upsert nodes
            for spec in nodes:
                payload: dict[str, Any] = {
                    "type": "qemu",
                    "template": spec.image,
                    "name": spec.name,
                    "icon": spec.icon or "Router.png",
                    "ethernet": max(1, spec.ethernet),
                    "left": int(spec.left),
                    "top": int(spec.top),
                }
                if spec.ram:
                    payload["ram"] = spec.ram
                if spec.cpu:
                    payload["cpu"] = spec.cpu

                ext_id = node_map.get(spec.local_id)
                if ext_id:
                    put = await client.put(f"{lab_api}/nodes/{ext_id}", json=payload)
                    if put.status_code >= 400:
                        logger.warning("update node %s failed: %s", ext_id, put.text[:200])
                else:
                    post = await client.post(f"{lab_api}/nodes", json=payload)
                    if post.status_code >= 400:
                        raise RuntimeError(
                            f"创建节点失败 ({spec.name}/{spec.image}): {post.text[:300]}"
                        )
                    try:
                        data = post.json().get("data") or {}
                        ext_id = str(data.get("id") or data.get("node_id") or "")
                    except Exception as exc:
                        raise RuntimeError(f"解析 Eve-NG 节点响应失败: {exc}") from exc
                    if not ext_id:
                        raise RuntimeError(f"Eve-NG 未返回节点 ID: {spec.name}")
                    node_map[spec.local_id] = ext_id

            # Best-effort links (Eve topology nets vary by version)
            for link in links:
                src = node_map.get(link.source_local_id)
                dst = node_map.get(link.target_local_id)
                if not src or not dst:
                    continue
                try:
                    await client.post(
                        f"{lab_api}/nodes/{src}/interfaces",
                        json={
                            "type": "ethernet",
                            "name": link.source_port,
                            "remote_id": int(dst) if str(dst).isdigit() else dst,
                            "remote_if": link.target_port,
                        },
                    )
                except Exception as exc:
                    logger.warning("link sync skipped: %s", exc)

        return LabSyncResult(
            lab_path=lab_path,
            node_map=node_map,
            message=f"已同步 {len(nodes)} 个节点到 Eve-NG",
        )

    async def _set_all(
        self, lab_path: str, node_map: dict[str, str], action: str
    ) -> LabStatusResult:
        async with await self._client() as client:
            await self._login(client)
            lab_api = self._lab_api_path(lab_path)
            statuses: dict[str, str] = {}
            for local_id, ext_id in node_map.items():
                resp = await client.get(f"{lab_api}/nodes/{ext_id}/{action}")
                if resp.status_code >= 400:
                    statuses[local_id] = "error"
                else:
                    statuses[local_id] = "running" if action == "start" else "stopped"
            overall = (
                "running"
                if action == "start" and any(v == "running" for v in statuses.values())
                else "stopped"
                if action == "stop"
                else "error"
            )
            return LabStatusResult(status=overall, node_status=statuses)

    async def start_lab(self, lab_path: str, node_map: dict[str, str]) -> LabStatusResult:
        return await self._set_all(lab_path, node_map, "start")

    async def stop_lab(self, lab_path: str, node_map: dict[str, str]) -> LabStatusResult:
        return await self._set_all(lab_path, node_map, "stop")

    async def get_status(self, lab_path: str, node_map: dict[str, str]) -> LabStatusResult:
        async with await self._client() as client:
            await self._login(client)
            lab_api = self._lab_api_path(lab_path)
            statuses: dict[str, str] = {}
            for local_id, ext_id in node_map.items():
                resp = await client.get(f"{lab_api}/nodes/{ext_id}")
                state = "stopped"
                if resp.status_code < 400:
                    try:
                        data = resp.json().get("data") or {}
                        raw = str(data.get("status") or data.get("state") or "0")
                        state = "running" if raw in ("2", "running", "started") else "stopped"
                    except Exception:
                        state = "stopped"
                else:
                    state = "error"
                statuses[local_id] = state
            overall = "running" if any(v == "running" for v in statuses.values()) else "stopped"
            return LabStatusResult(status=overall, node_status=statuses)

    async def console_url(self, lab_path: str, external_node_id: str) -> str | None:
        # Eve HTML5 console typically: /html5/#/lab/... or /api/labs/.../nodes/{id}/console
        path = lab_path if lab_path.startswith("/") else f"/{lab_path}"
        return f"{self._base()}/legacy/#/lab{path}/node/{external_node_id}"
