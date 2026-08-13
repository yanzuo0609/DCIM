import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_network_model_design_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse, PaginationParams
from app.schemas.network_model_design import (
    CategoryAttributeSchema,
    NetworkDesignModelCreate,
    NetworkDesignModelResponse,
    NetworkDesignModelUpdate,
    NetworkModelFolderCreate,
    NetworkModelFolderResponse,
    NetworkModelFolderTreeNode,
    NetworkModelFolderUpdate,
    NetworkWiringRuleCreate,
    NetworkWiringRuleResponse,
    NetworkWiringRuleUpdate,
    TaxonomyCategory,
)
from app.services.network_model_design import NetworkModelDesignService

router = APIRouter(prefix="/network-model-design")


@router.get("/taxonomy", response_model=ApiResponse[list[TaxonomyCategory]])
async def get_taxonomy(
    service: Annotated[NetworkModelDesignService, Depends(get_network_model_design_service)],
    _: Annotated[User, Depends(require_permissions("network:view"))],
) -> ApiResponse[list[TaxonomyCategory]]:
    return ApiResponse(data=service.get_taxonomy(), timestamp=datetime.now())


@router.get("/attribute-schema/{category}", response_model=ApiResponse[CategoryAttributeSchema])
async def get_attribute_schema(
    category: str,
    service: Annotated[NetworkModelDesignService, Depends(get_network_model_design_service)],
    _: Annotated[User, Depends(require_permissions("network:view"))],
    subtype: str | None = None,
) -> ApiResponse[CategoryAttributeSchema]:
    return ApiResponse(
        data=service.get_attribute_schema(category, subtype),
        timestamp=datetime.now(),
    )


@router.get("/folders/tree", response_model=ApiResponse[list[NetworkModelFolderTreeNode]])
async def list_folder_tree(
    service: Annotated[NetworkModelDesignService, Depends(get_network_model_design_service)],
    _: Annotated[User, Depends(require_permissions("network:view"))],
) -> ApiResponse[list[NetworkModelFolderTreeNode]]:
    data = await service.list_folder_tree()
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/folders", response_model=ApiResponse[NetworkModelFolderResponse], status_code=201)
async def create_folder(
    payload: NetworkModelFolderCreate,
    service: Annotated[NetworkModelDesignService, Depends(get_network_model_design_service)],
    current_user: Annotated[User, Depends(require_permissions("network:create"))],
) -> ApiResponse[NetworkModelFolderResponse]:
    data = await service.create_folder(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/folders/{folder_id}", response_model=ApiResponse[NetworkModelFolderResponse])
async def update_folder(
    folder_id: uuid.UUID,
    payload: NetworkModelFolderUpdate,
    service: Annotated[NetworkModelDesignService, Depends(get_network_model_design_service)],
    current_user: Annotated[User, Depends(require_permissions("network:update"))],
) -> ApiResponse[NetworkModelFolderResponse]:
    data = await service.update_folder(folder_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/folders/{folder_id}", response_model=ApiResponse[dict[str, str]])
async def delete_folder(
    folder_id: uuid.UUID,
    service: Annotated[NetworkModelDesignService, Depends(get_network_model_design_service)],
    current_user: Annotated[User, Depends(require_permissions("network:delete"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete_folder(folder_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())


@router.get("/models", response_model=PaginatedResponse[NetworkDesignModelResponse])
async def list_models(
    service: Annotated[NetworkModelDesignService, Depends(get_network_model_design_service)],
    _: Annotated[User, Depends(require_permissions("network:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    keyword: str | None = None,
    sort: str = "updated_at",
    order: str = "desc",
    folder_id: uuid.UUID | None = None,
    category: str | None = None,
    subtype: str | None = None,
    published_only: bool = False,
    include_descendants: bool = False,
) -> PaginatedResponse[NetworkDesignModelResponse]:
    params = PaginationParams(
        page=page, page_size=page_size, keyword=keyword, sort=sort, order=order
    )
    items, pagination = await service.list_models(
        params,
        folder_id=folder_id,
        include_descendants=include_descendants,
        category=category,
        subtype=subtype,
        published_only=published_only,
    )
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post("/models", response_model=ApiResponse[NetworkDesignModelResponse], status_code=201)
async def create_model(
    payload: NetworkDesignModelCreate,
    service: Annotated[NetworkModelDesignService, Depends(get_network_model_design_service)],
    current_user: Annotated[User, Depends(require_permissions("network:create"))],
) -> ApiResponse[NetworkDesignModelResponse]:
    data = await service.create_model(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get("/models/{model_id}", response_model=ApiResponse[NetworkDesignModelResponse])
async def get_model(
    model_id: uuid.UUID,
    service: Annotated[NetworkModelDesignService, Depends(get_network_model_design_service)],
    _: Annotated[User, Depends(require_permissions("network:view"))],
) -> ApiResponse[NetworkDesignModelResponse]:
    data = await service.get_model(model_id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/models/{model_id}", response_model=ApiResponse[NetworkDesignModelResponse])
async def update_model(
    model_id: uuid.UUID,
    payload: NetworkDesignModelUpdate,
    service: Annotated[NetworkModelDesignService, Depends(get_network_model_design_service)],
    current_user: Annotated[User, Depends(require_permissions("network:update"))],
) -> ApiResponse[NetworkDesignModelResponse]:
    data = await service.update_model(model_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/models/{model_id}", response_model=ApiResponse[dict[str, str]])
async def delete_model(
    model_id: uuid.UUID,
    service: Annotated[NetworkModelDesignService, Depends(get_network_model_design_service)],
    current_user: Annotated[User, Depends(require_permissions("network:delete"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete_model(model_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())


@router.get(
    "/wiring-rules",
    response_model=ApiResponse[list[NetworkWiringRuleResponse]],
)
async def list_wiring_rules(
    service: Annotated[NetworkModelDesignService, Depends(get_network_model_design_service)],
    _: Annotated[User, Depends(require_permissions("network:view"))],
    project_id: uuid.UUID | None = Query(None),
    topology_id: uuid.UUID | None = Query(None),
) -> ApiResponse[list[NetworkWiringRuleResponse]]:
    data = await service.list_wiring_rules(project_id=project_id, topology_id=topology_id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post(
    "/wiring-rules",
    response_model=ApiResponse[NetworkWiringRuleResponse],
    status_code=201,
)
async def create_wiring_rule(
    payload: NetworkWiringRuleCreate,
    service: Annotated[NetworkModelDesignService, Depends(get_network_model_design_service)],
    current_user: Annotated[User, Depends(require_permissions("network:create"))],
) -> ApiResponse[NetworkWiringRuleResponse]:
    data = await service.create_wiring_rule(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put(
    "/wiring-rules/{rule_id}",
    response_model=ApiResponse[NetworkWiringRuleResponse],
)
async def update_wiring_rule(
    rule_id: uuid.UUID,
    payload: NetworkWiringRuleUpdate,
    service: Annotated[NetworkModelDesignService, Depends(get_network_model_design_service)],
    current_user: Annotated[User, Depends(require_permissions("network:update"))],
) -> ApiResponse[NetworkWiringRuleResponse]:
    data = await service.update_wiring_rule(rule_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete(
    "/wiring-rules/{rule_id}",
    response_model=ApiResponse[dict[str, str]],
)
async def delete_wiring_rule(
    rule_id: uuid.UUID,
    service: Annotated[NetworkModelDesignService, Depends(get_network_model_design_service)],
    current_user: Annotated[User, Depends(require_permissions("network:delete"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete_wiring_rule(rule_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())
