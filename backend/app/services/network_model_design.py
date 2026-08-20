import math
import uuid
from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.network_model_taxonomy import (
    TAXONOMY,
    attribute_schema,
    default_attributes,
    merge_defaults,
)
from app.models.network_model_design import (
    NetworkDesignModel,
    NetworkModelFolder,
    NetworkWiringRule,
)
from app.models.network import NetworkProject, NetworkTopology
from app.repositories.network_model_design import (
    NetworkDesignModelRepository,
    NetworkModelFolderRepository,
    NetworkWiringRuleRepository,
)
from app.schemas.common import PaginationMeta, PaginationParams
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
from app.schemas.wiring_rule_config import normalize_wiring_config


def _pagination(params: PaginationParams, total: int) -> PaginationMeta:
    pages = max(1, math.ceil(total / params.page_size)) if total else 1
    return PaginationMeta(page=params.page, page_size=params.page_size, total=total, pages=pages)


def _model_response(entity: NetworkDesignModel) -> NetworkDesignModelResponse:
    """所有模型响应统一应用分类默认值和旧数据迁移，避免列表/详情显示过期属性。"""
    response = NetworkDesignModelResponse.model_validate(entity)
    normalized = merge_defaults(entity.category, entity.subtype, entity.attributes)
    return response.model_copy(update={"attributes": normalized})

class NetworkModelDesignService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.folder_repo = NetworkModelFolderRepository(session)
        self.model_repo = NetworkDesignModelRepository(session)
        self.rule_repo = NetworkWiringRuleRepository(session)

    # ── taxonomy ────────────────────────────────────────────────────

    def get_taxonomy(self) -> list[TaxonomyCategory]:
        return TAXONOMY

    def get_attribute_schema(self, category: str, subtype: str | None = None) -> CategoryAttributeSchema:
        schema = attribute_schema(category)
        if subtype:
            schema = CategoryAttributeSchema(
                category=schema.category,
                fields=schema.fields,
                default_attributes=default_attributes(category, subtype),
            )
        return schema

    # ── folders ─────────────────────────────────────────────────────

    async def list_folder_tree(self) -> list[NetworkModelFolderTreeNode]:
        folders = await self.folder_repo.list_all()
        by_parent: dict[uuid.UUID | None, list[NetworkModelFolder]] = {}
        for f in folders:
            by_parent.setdefault(f.parent_id, []).append(f)

        async def build(parent_id: uuid.UUID | None) -> list[NetworkModelFolderTreeNode]:
            nodes: list[NetworkModelFolderTreeNode] = []
            for f in by_parent.get(parent_id, []):
                count = await self.folder_repo.count_models(f.id)
                node = NetworkModelFolderTreeNode(
                    id=f.id,
                    parent_id=f.parent_id,
                    kind=f.kind,
                    name=f.name,
                    code=f.code,
                    description=f.description,
                    sort_order=f.sort_order,
                    created_at=f.created_at,
                    updated_at=f.updated_at,
                    children=await build(f.id),
                    model_count=count,
                )
                nodes.append(node)
            return nodes

        return await build(None)

    async def create_folder(
        self, payload: NetworkModelFolderCreate, *, user_id: uuid.UUID | None
    ) -> NetworkModelFolderResponse:
        if payload.parent_id:
            parent = await self.folder_repo.get_by_id(payload.parent_id)
            if not parent:
                raise NotFoundError("父级文件夹不存在")
        entity = NetworkModelFolder(
            **payload.model_dump(),
            created_by=user_id,
            updated_by=user_id,
        )
        await self.folder_repo.create(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return NetworkModelFolderResponse.model_validate(entity)

    async def update_folder(
        self,
        folder_id: uuid.UUID,
        payload: NetworkModelFolderUpdate,
        *,
        user_id: uuid.UUID | None,
    ) -> NetworkModelFolderResponse:
        entity = await self.folder_repo.get_by_id(folder_id)
        if not entity:
            raise NotFoundError("文件夹/项目不存在")
        data = payload.model_dump(exclude_unset=True)
        if "parent_id" in data and data["parent_id"] == folder_id:
            raise ValidationError("不能将自身设为父级")
        for key, value in data.items():
            setattr(entity, key, value)
        entity.updated_by = user_id
        entity.version = (entity.version or 1) + 1
        await self.session.commit()
        await self.session.refresh(entity)
        return NetworkModelFolderResponse.model_validate(entity)

    async def delete_folder(self, folder_id: uuid.UUID, *, user_id: uuid.UUID | None) -> None:
        entity = await self.folder_repo.get_by_id(folder_id)
        if not entity:
            raise NotFoundError("文件夹/项目不存在")
        linked_project = await self.session.scalar(
            select(NetworkProject.id)
            .where(
                NetworkProject.model_root_folder_id == folder_id,
                NetworkProject.deleted_at.is_(None),
            )
            .limit(1)
        )
        if linked_project is not None:
            raise ConflictError("该文件夹/项目仍被网络项目关联，请先解除关联")
        count = await self.folder_repo.count_models(folder_id)
        children = [f for f in await self.folder_repo.list_all() if f.parent_id == folder_id]
        if count or children:
            raise ConflictError("请先删除子文件夹与模型后再删除")
        await self.folder_repo.soft_delete(entity, deleted_by=user_id)
        await self.session.commit()

    # ── models ──────────────────────────────────────────────────────

    async def list_models(
        self,
        params: PaginationParams,
        *,
        folder_id: uuid.UUID | None = None,
        include_descendants: bool = False,
        category: str | None = None,
        subtype: str | None = None,
        published_only: bool = False,
    ) -> tuple[list[NetworkDesignModelResponse], PaginationMeta]:
        filters: dict = {}
        in_filters: dict | None = None
        if folder_id:
            if include_descendants:
                folder_ids = await self._descendant_folder_ids(folder_id)
                in_filters = {"folder_id": folder_ids}
            else:
                filters["folder_id"] = folder_id
        if category:
            filters["category"] = category
        if subtype:
            filters["subtype"] = subtype
        if published_only:
            filters["is_published"] = True
        items, total = await self.model_repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            sort=params.sort,
            order=params.order,
            filters=filters or None,
            in_filters=in_filters,
            search_fields=["code", "name", "manufacturer_name", "vendor_sku", "contract_device_name"],
        )
        return [_model_response(i) for i in items], _pagination(params, total)

    async def _descendant_folder_ids(self, root_id: uuid.UUID) -> list[uuid.UUID]:
        root = await self.folder_repo.get_by_id(root_id)
        if not root:
            raise NotFoundError("文件夹/项目不存在")
        all_folders = await self.folder_repo.list_all()

        def _key(value: uuid.UUID | None) -> str | None:
            return str(value) if value is not None else None

        by_parent: dict[str | None, list[NetworkModelFolder]] = {}
        for f in all_folders:
            by_parent.setdefault(_key(f.parent_id), []).append(f)
        out = [root.id]
        stack = [root.id]
        seen = {root.id}
        while stack:
            cur = stack.pop()
            for child in by_parent.get(_key(cur), []):
                if child.id in seen:
                    continue
                seen.add(child.id)
                out.append(child.id)
                stack.append(child.id)
        return out

    async def get_model(self, model_id: uuid.UUID) -> NetworkDesignModelResponse:
        entity = await self.model_repo.get_by_id(model_id)
        if not entity:
            raise NotFoundError("模型不存在")
        return _model_response(entity)

    async def create_model(
        self, payload: NetworkDesignModelCreate, *, user_id: uuid.UUID | None
    ) -> NetworkDesignModelResponse:
        folder = await self.folder_repo.get_by_id(payload.folder_id)
        if not folder:
            raise NotFoundError("所属文件夹/项目不存在")
        if await self.model_repo.get_by_code(payload.code.strip()):
            raise ConflictError(f"模型编码已存在：{payload.code}")
        attrs = merge_defaults(payload.category, payload.subtype, payload.attributes)
        data = payload.model_dump()
        data["attributes"] = attrs
        if data.get("port_layout") is not None:
            data["port_layout"] = deepcopy(data["port_layout"])
        entity = NetworkDesignModel(**data, created_by=user_id, updated_by=user_id)
        await self.model_repo.create(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return _model_response(entity)

    async def update_model(
        self,
        model_id: uuid.UUID,
        payload: NetworkDesignModelUpdate,
        *,
        user_id: uuid.UUID | None,
    ) -> NetworkDesignModelResponse:
        entity = await self.model_repo.get_by_id(model_id)
        if not entity:
            raise NotFoundError("模型不存在")
        data = payload.model_dump(exclude_unset=True)
        if "code" in data and data["code"]:
            other = await self.model_repo.get_by_code(data["code"].strip())
            if other and other.id != entity.id:
                raise ConflictError(f"模型编码已存在：{data['code']}")
        if "folder_id" in data and data["folder_id"]:
            folder = await self.folder_repo.get_by_id(data["folder_id"])
            if not folder:
                raise NotFoundError("所属文件夹/项目不存在")
        category = data.get("category", entity.category)
        subtype = data.get("subtype", entity.subtype)
        if "attributes" in data:
            data["attributes"] = merge_defaults(category, subtype, data["attributes"])
        if "port_layout" in data and data["port_layout"] is not None:
            data["port_layout"] = deepcopy(data["port_layout"])
        for key, value in data.items():
            setattr(entity, key, value)
        entity.updated_by = user_id
        entity.version = (entity.version or 1) + 1
        await self.session.commit()
        await self.session.refresh(entity)
        return _model_response(entity)

    async def delete_model(self, model_id: uuid.UUID, *, user_id: uuid.UUID | None) -> None:
        entity = await self.model_repo.get_by_id(model_id)
        if not entity:
            raise NotFoundError("模型不存在")
        await self.model_repo.soft_delete(entity, deleted_by=user_id)
        await self.session.commit()

    # ── wiring rules（全局：所有项目通用）────────────────────────────

    async def _optional_project_id(
        self,
        *,
        project_id: uuid.UUID | None,
        topology_id: uuid.UUID | None,
    ) -> uuid.UUID | None:
        """解析可选的项目溯源 ID，不强制。"""
        if project_id:
            project = await self.session.get(NetworkProject, project_id)
            if not project or project.deleted_at is not None:
                raise NotFoundError("项目不存在")
            return project_id
        if topology_id:
            topo = await self.session.get(NetworkTopology, topology_id)
            if not topo or topo.deleted_at is not None:
                raise NotFoundError("拓扑不存在")
            return topo.project_id
        return None

    async def list_wiring_rules(
        self,
        *,
        project_id: uuid.UUID | None = None,
        topology_id: uuid.UUID | None = None,
    ) -> list[NetworkWiringRuleResponse]:
        # 规则全局通用；保留 query 参数仅兼容旧前端，忽略过滤
        _ = project_id, topology_id
        items = await self.rule_repo.list_all()
        return [NetworkWiringRuleResponse.model_validate(i) for i in items]

    async def create_wiring_rule(
        self, payload: NetworkWiringRuleCreate, *, user_id: uuid.UUID | None
    ) -> NetworkWiringRuleResponse:
        if not (payload.name or "").strip():
            raise ValidationError("规则名称不能为空")
        pid = await self._optional_project_id(
            project_id=payload.project_id,
            topology_id=payload.topology_id,
        )
        data = payload.model_dump()
        data["project_id"] = pid
        data["topology_id"] = payload.topology_id
        data["config"] = normalize_wiring_config(data.get("config"))
        entity = NetworkWiringRule(**data, created_by=user_id, updated_by=user_id)
        await self.rule_repo.create(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return NetworkWiringRuleResponse.model_validate(entity)

    async def update_wiring_rule(
        self,
        rule_id: uuid.UUID,
        payload: NetworkWiringRuleUpdate,
        *,
        user_id: uuid.UUID | None,
    ) -> NetworkWiringRuleResponse:
        entity = await self.rule_repo.get_by_id(rule_id)
        if not entity:
            raise NotFoundError("布线规则不存在")
        data = payload.model_dump(exclude_unset=True)
        if "config" in data:
            data["config"] = normalize_wiring_config(data.get("config"))
        for key, value in data.items():
            setattr(entity, key, value)
        entity.updated_by = user_id
        entity.version = (entity.version or 1) + 1
        await self.session.commit()
        await self.session.refresh(entity)
        return NetworkWiringRuleResponse.model_validate(entity)

    async def delete_wiring_rule(self, rule_id: uuid.UUID, *, user_id: uuid.UUID | None) -> None:
        entity = await self.rule_repo.get_by_id(rule_id)
        if not entity:
            raise NotFoundError("布线规则不存在")
        await self.rule_repo.soft_delete(entity, deleted_by=user_id)
        await self.session.commit()
