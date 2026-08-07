"""Lab engine abstraction for topology simulation (Eve-NG / GNS3)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LabNodeSpec:
    local_id: str
    name: str
    image: str
    left: int = 100
    top: int = 100
    icon: str | None = None
    ram: int | None = None
    cpu: int | None = None
    ethernet: int = 8


@dataclass
class LabLinkSpec:
    source_local_id: str
    source_port: str
    target_local_id: str
    target_port: str


@dataclass
class LabSyncResult:
    lab_path: str
    node_map: dict[str, str] = field(default_factory=dict)
    message: str = ""


@dataclass
class LabStatusResult:
    status: str
    node_status: dict[str, str] = field(default_factory=dict)
    message: str = ""


class LabEngine(ABC):
    name: str = "none"

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    async def sync_lab(
        self,
        *,
        lab_name: str,
        existing_path: str | None,
        nodes: list[LabNodeSpec],
        links: list[LabLinkSpec],
        existing_node_map: dict[str, str] | None = None,
    ) -> LabSyncResult: ...

    @abstractmethod
    async def start_lab(self, lab_path: str, node_map: dict[str, str]) -> LabStatusResult: ...

    @abstractmethod
    async def stop_lab(self, lab_path: str, node_map: dict[str, str]) -> LabStatusResult: ...

    @abstractmethod
    async def get_status(self, lab_path: str, node_map: dict[str, str]) -> LabStatusResult: ...

    @abstractmethod
    async def console_url(self, lab_path: str, external_node_id: str) -> str | None: ...


class NoneLabEngine(LabEngine):
    name = "none"

    def is_configured(self) -> bool:
        return False

    async def sync_lab(self, **kwargs: Any) -> LabSyncResult:
        raise RuntimeError("未配置仿真引擎。请设置 LAB_ENGINE=eve-ng 及 Eve-NG 连接参数。")

    async def start_lab(self, lab_path: str, node_map: dict[str, str]) -> LabStatusResult:
        raise RuntimeError("未配置仿真引擎")

    async def stop_lab(self, lab_path: str, node_map: dict[str, str]) -> LabStatusResult:
        raise RuntimeError("未配置仿真引擎")

    async def get_status(self, lab_path: str, node_map: dict[str, str]) -> LabStatusResult:
        return LabStatusResult(status="idle", message="仿真引擎未启用")

    async def console_url(self, lab_path: str, external_node_id: str) -> str | None:
        return None
