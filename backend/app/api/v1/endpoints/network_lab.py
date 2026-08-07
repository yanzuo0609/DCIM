import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.core.dependencies import require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.network import (
    LabConsoleResponse,
    LabEngineInfoResponse,
    NetworkLabSessionResponse,
)
from app.services.lab import TopologyLabService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/network-topologies")


def get_topology_lab_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TopologyLabService:
    return TopologyLabService(session)


@router.get("/lab/engine", response_model=ApiResponse[LabEngineInfoResponse])
async def lab_engine_info(
    service: Annotated[TopologyLabService, Depends(get_topology_lab_service)],
    _: Annotated[User, Depends(require_permissions("network:view"))],
) -> ApiResponse[LabEngineInfoResponse]:
    return ApiResponse(data=service.engine_info(), timestamp=datetime.now())


@router.get("/{topology_id}/lab", response_model=ApiResponse[NetworkLabSessionResponse])
async def get_lab_session(
    topology_id: uuid.UUID,
    service: Annotated[TopologyLabService, Depends(get_topology_lab_service)],
    _: Annotated[User, Depends(require_permissions("network:view"))],
) -> ApiResponse[NetworkLabSessionResponse]:
    data = await service.get_session(topology_id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/{topology_id}/lab/sync", response_model=ApiResponse[NetworkLabSessionResponse])
async def sync_lab(
    topology_id: uuid.UUID,
    service: Annotated[TopologyLabService, Depends(get_topology_lab_service)],
    current_user: Annotated[User, Depends(require_permissions("network:update"))],
) -> ApiResponse[NetworkLabSessionResponse]:
    data = await service.sync(topology_id, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/{topology_id}/lab/start", response_model=ApiResponse[NetworkLabSessionResponse])
async def start_lab(
    topology_id: uuid.UUID,
    service: Annotated[TopologyLabService, Depends(get_topology_lab_service)],
    current_user: Annotated[User, Depends(require_permissions("network:update"))],
) -> ApiResponse[NetworkLabSessionResponse]:
    data = await service.start(topology_id, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/{topology_id}/lab/stop", response_model=ApiResponse[NetworkLabSessionResponse])
async def stop_lab(
    topology_id: uuid.UUID,
    service: Annotated[TopologyLabService, Depends(get_topology_lab_service)],
    current_user: Annotated[User, Depends(require_permissions("network:update"))],
) -> ApiResponse[NetworkLabSessionResponse]:
    data = await service.stop(topology_id, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get("/{topology_id}/lab/status", response_model=ApiResponse[NetworkLabSessionResponse])
async def lab_status(
    topology_id: uuid.UUID,
    service: Annotated[TopologyLabService, Depends(get_topology_lab_service)],
    _: Annotated[User, Depends(require_permissions("network:view"))],
) -> ApiResponse[NetworkLabSessionResponse]:
    data = await service.refresh_status(topology_id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get(
    "/{topology_id}/lab/console/{node_id}",
    response_model=ApiResponse[LabConsoleResponse],
)
async def lab_console(
    topology_id: uuid.UUID,
    node_id: uuid.UUID,
    service: Annotated[TopologyLabService, Depends(get_topology_lab_service)],
    _: Annotated[User, Depends(require_permissions("network:view"))],
) -> ApiResponse[LabConsoleResponse]:
    data = await service.console(topology_id, node_id)
    return ApiResponse(data=data, timestamp=datetime.now())
