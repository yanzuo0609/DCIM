"""Lab engine factory and topology lab orchestration."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.network import NetworkLabSession, NetworkNode, NetworkTopology
from app.models.network_model_design import NetworkDesignModel
from app.schemas.network import (
    LabConsoleResponse,
    LabEngineInfoResponse,
    NetworkLabSessionResponse,
)
from app.services.lab.base import LabEngine, LabLinkSpec, LabNodeSpec, NoneLabEngine
from app.services.lab.eve_ng import EveNgAdapter
from app.services.lab.mock import MockLabEngine

logger = logging.getLogger(__name__)


def get_lab_engine(settings: Settings | None = None) -> LabEngine:
    cfg = settings or get_settings()
    engine = (cfg.lab_engine or "none").strip().lower()
    # auto: 有 Eve-NG URL 则用 eve-ng，否则开发态用 mock
    if engine in ("", "none", "auto"):
        if cfg.eve_ng_base_url.strip():
            engine = "eve-ng"
        elif cfg.debug:
            engine = "mock"
        else:
            engine = "none"
    if engine == "eve-ng":
        return EveNgAdapter(cfg)
    if engine == "mock":
        return MockLabEngine()
    return NoneLabEngine()


def _safe_int(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _str_dict(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, val in raw.items():
        if val is None:
            continue
        out[str(key)] = str(val)
    return out


class TopologyLabService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.engine = get_lab_engine(self.settings)

    def engine_info(self) -> LabEngineInfoResponse:
        configured = self.engine.is_configured()
        if configured:
            if self.engine.name == "mock":
                message = "本地模拟引擎已启用（不连接 Eve-NG）。生产环境可设置 LAB_ENGINE=eve-ng 与 EVE_NG_BASE_URL。"
            elif self.engine.name == "eve-ng":
                message = f"Eve-NG 已配置：{self.settings.eve_ng_base_url}"
            else:
                message = None
        else:
            message = "未配置仿真引擎。设置 LAB_ENGINE=mock 或 LAB_ENGINE=eve-ng 与 EVE_NG_BASE_URL 后可用。"
        return LabEngineInfoResponse(
            engine=self.engine.name,
            configured=configured,
            base_url=self.settings.eve_ng_base_url or None if self.engine.name == "eve-ng" else None,
            message=message,
        )

    def _to_response(self, session: NetworkLabSession) -> NetworkLabSessionResponse:
        return NetworkLabSessionResponse(
            id=session.id,
            topology_id=session.topology_id,
            engine=session.engine or self.engine.name,
            external_lab_path=session.external_lab_path,
            status=session.status or "idle",
            last_sync_at=session.last_sync_at,
            error_message=session.error_message,
            node_map=_str_dict(session.node_map) or None,
            node_status=_str_dict(session.node_status) or None,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    async def _get_topology(self, topology_id: uuid.UUID) -> NetworkTopology:
        entity = await self.session.get(NetworkTopology, topology_id)
        if not entity or entity.deleted_at is not None:
            raise NotFoundError("Network topology not found")
        return entity

    async def _get_or_create_session(self, topology_id: uuid.UUID) -> NetworkLabSession:
        stmt = select(NetworkLabSession).where(
            NetworkLabSession.topology_id == topology_id,
            NetworkLabSession.deleted_at.is_(None),
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing
        session = NetworkLabSession(
            topology_id=topology_id,
            engine=self.engine.name,
            status="idle",
            node_map={},
            node_status={},
        )
        self.session.add(session)
        await self.session.flush()
        return session

    async def get_session(self, topology_id: uuid.UUID) -> NetworkLabSessionResponse:
        await self._get_topology(topology_id)
        session = await self._get_or_create_session(topology_id)
        return self._to_response(session)

    def _sim_image_from_model(self, model: NetworkDesignModel | None, kind: str) -> str:
        attrs = (model.attributes if model and isinstance(model.attributes, dict) else {}) or {}
        image = str(attrs.get("sim_image") or "").strip()
        if image:
            return image
        if kind == "switch":
            return "viosl2"
        if kind == "security":
            return "asav"
        if kind == "server":
            return "linux"
        return "vios"

    async def sync(self, topology_id: uuid.UUID, user_id: uuid.UUID | None = None) -> NetworkLabSessionResponse:
        topo = await self._get_topology(topology_id)
        if not self.engine.is_configured():
            raise ValidationError(self.engine_info().message or "仿真引擎未配置")

        nodes_stmt = select(NetworkNode).where(
            NetworkNode.topology_id == topology_id,
            NetworkNode.deleted_at.is_(None),
            NetworkNode.on_canvas.is_(True),
        )
        nodes = list((await self.session.execute(nodes_stmt)).scalars().all())
        if not nodes:
            raise ValidationError("画布上没有可同步的设备节点")

        model_ids = [n.design_model_id for n in nodes if n.design_model_id]
        models: dict[uuid.UUID, NetworkDesignModel] = {}
        if model_ids:
            m_stmt = select(NetworkDesignModel).where(NetworkDesignModel.id.in_(model_ids))
            for m in (await self.session.execute(m_stmt)).scalars().all():
                models[m.id] = m

        specs: list[LabNodeSpec] = []
        for n in nodes:
            model = models.get(n.design_model_id) if n.design_model_id else None
            attrs = (model.attributes if model and isinstance(model.attributes, dict) else {}) or {}
            eth = max(4, _safe_int(n.switch_port_count, 8) or 8)
            specs.append(
                LabNodeSpec(
                    local_id=str(n.id),
                    name=n.name or str(n.id)[:8],
                    image=self._sim_image_from_model(model, n.kind or "switch"),
                    left=int(n.pos_x or 100),
                    top=int(n.pos_y or 100),
                    icon=str(attrs.get("sim_icon") or "") or None,
                    ram=_safe_int(attrs.get("sim_ram")),
                    cpu=_safe_int(attrs.get("sim_cpu")),
                    ethernet=eth,
                )
            )

        from app.models.network import NetworkLink

        links_stmt = select(NetworkLink).where(
            NetworkLink.topology_id == topology_id,
            NetworkLink.deleted_at.is_(None),
        )
        links_db = list((await self.session.execute(links_stmt)).scalars().all())
        link_specs = [
            LabLinkSpec(
                source_local_id=str(lk.source_node_id),
                source_port=str(lk.source_port or ""),
                target_local_id=str(lk.target_node_id),
                target_port=str(lk.target_port or ""),
            )
            for lk in links_db
        ]

        session = await self._get_or_create_session(topology_id)
        try:
            result = await self.engine.sync_lab(
                lab_name=topo.name or f"topo-{topology_id}",
                existing_path=session.external_lab_path,
                nodes=specs,
                links=link_specs,
                existing_node_map=_str_dict(session.node_map),
            )
            session.external_lab_path = result.lab_path
            session.node_map = _str_dict(result.node_map)
            session.node_status = _str_dict(session.node_status)
            session.status = "synced"
            session.error_message = None
            session.last_sync_at = datetime.now(timezone.utc)
            session.engine = self.engine.name
            session.updated_by = user_id
        except ValidationError:
            raise
        except Exception as exc:
            logger.exception("lab sync failed topology=%s", topology_id)
            session.status = "error"
            session.error_message = str(exc)[:1000]
            session.updated_by = user_id
            await self.session.flush()
            raise ValidationError(f"同步实验室失败：{exc}") from exc

        await self.session.flush()
        try:
            return self._to_response(session)
        except Exception as exc:
            logger.exception("lab sync response build failed")
            raise ValidationError(f"同步成功但响应序列化失败：{exc}") from exc

    async def start(self, topology_id: uuid.UUID, user_id: uuid.UUID | None = None) -> NetworkLabSessionResponse:
        session = await self._require_synced(topology_id)
        try:
            result = await self.engine.start_lab(
                session.external_lab_path or "",
                _str_dict(session.node_map),
            )
            session.status = result.status
            session.node_status = _str_dict(result.node_status)
            session.error_message = None
            session.updated_by = user_id
        except Exception as exc:
            session.status = "error"
            session.error_message = str(exc)[:1000]
            await self.session.flush()
            raise ValidationError(f"启动实验室失败：{exc}") from exc
        await self.session.flush()
        return self._to_response(session)

    async def stop(self, topology_id: uuid.UUID, user_id: uuid.UUID | None = None) -> NetworkLabSessionResponse:
        session = await self._require_synced(topology_id)
        try:
            result = await self.engine.stop_lab(
                session.external_lab_path or "",
                _str_dict(session.node_map),
            )
            session.status = result.status
            session.node_status = _str_dict(result.node_status)
            session.error_message = None
            session.updated_by = user_id
        except Exception as exc:
            session.status = "error"
            session.error_message = str(exc)[:1000]
            await self.session.flush()
            raise ValidationError(f"停止实验室失败：{exc}") from exc
        await self.session.flush()
        return self._to_response(session)

    async def refresh_status(self, topology_id: uuid.UUID) -> NetworkLabSessionResponse:
        session = await self._get_or_create_session(topology_id)
        if not session.external_lab_path or not session.node_map:
            return self._to_response(session)
        if not self.engine.is_configured():
            return self._to_response(session)
        try:
            result = await self.engine.get_status(
                session.external_lab_path,
                _str_dict(session.node_map),
            )
            session.status = result.status
            session.node_status = _str_dict(result.node_status)
            session.error_message = None
        except Exception as exc:
            session.error_message = str(exc)[:1000]
        await self.session.flush()
        return self._to_response(session)

    async def console(self, topology_id: uuid.UUID, node_id: uuid.UUID) -> LabConsoleResponse:
        session = await self._require_synced(topology_id)
        ext = _str_dict(session.node_map).get(str(node_id))
        if not ext:
            raise ValidationError("该节点尚未同步到实验室")
        url = await self.engine.console_url(session.external_lab_path or "", ext)
        return LabConsoleResponse(
            node_id=node_id,
            console_url=url,
            message=None if url else "引擎未提供控制台地址",
        )

    async def _require_synced(self, topology_id: uuid.UUID) -> NetworkLabSession:
        await self._get_topology(topology_id)
        session = await self._get_or_create_session(topology_id)
        if not session.external_lab_path or not session.node_map:
            raise ValidationError("请先执行「同步到实验室」")
        if not self.engine.is_configured():
            raise ValidationError(self.engine_info().message or "仿真引擎未配置")
        return session
