"""Personnel management schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OrgNodePayload(BaseModel):
    id: str | None = None
    parent_id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    role_title: str | None = None
    person_name: str | None = None
    phone: str | None = None
    email: str | None = None
    pos_x: float = 0
    pos_y: float = 0
    sort_order: int = 0


class OrgLinkPayload(BaseModel):
    id: str | None = None
    source_node_id: str
    target_node_id: str


class OrgChartCreate(BaseModel):
    project_no: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)


class OrgChartUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    project_no: str | None = Field(default=None, min_length=1, max_length=100)
    nodes: list[OrgNodePayload] | None = None
    links: list[OrgLinkPayload] | None = None
    canvas_json: dict | list | None = None


class OrgNodeResponse(BaseModel):
    id: str
    chart_id: str
    parent_id: str | None = None
    title: str
    role_title: str | None = None
    person_name: str | None = None
    phone: str | None = None
    email: str | None = None
    pos_x: float
    pos_y: float
    sort_order: int


class OrgLinkResponse(BaseModel):
    id: str
    chart_id: str
    source_node_id: str
    target_node_id: str


class OrgChartBrief(BaseModel):
    id: str
    project_no: str
    name: str
    node_count: int = 0
    created_at: datetime
    updated_at: datetime


class OrgChartResponse(BaseModel):
    id: str
    project_no: str
    name: str
    canvas_json: dict | list | None = None
    nodes: list[OrgNodeResponse] = Field(default_factory=list)
    links: list[OrgLinkResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class InternalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role_title: str = Field(default="", max_length=100)
    phone: str | None = None
    email: str | None = None
    company: str | None = None
    project_no: str | None = None
    org_node_id: str | None = None
    notes: str | None = None


class InternalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    role_title: str | None = None
    phone: str | None = None
    email: str | None = None
    company: str | None = None
    project_no: str | None = None
    org_node_id: str | None = None
    notes: str | None = None


class InternalResponse(BaseModel):
    id: str
    name: str
    role_title: str
    phone: str | None = None
    email: str | None = None
    company: str | None = None
    project_no: str | None = None
    org_node_id: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class SupplierProductPayload(BaseModel):
    device_model_id: str | None = None
    device_name: str | None = None
    device_model_name: str | None = None


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role_title: str = Field(default="", max_length=100)
    phone: str | None = None
    email: str | None = None
    wechat: str | None = None
    manufacturer_id: str
    notes: str | None = None
    contract_ids: list[str] = Field(default_factory=list)
    products: list[SupplierProductPayload] = Field(default_factory=list)


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    role_title: str | None = None
    phone: str | None = None
    email: str | None = None
    wechat: str | None = None
    manufacturer_id: str | None = None
    notes: str | None = None
    contract_ids: list[str] | None = None
    products: list[SupplierProductPayload] | None = None


class SupplierProductResponse(BaseModel):
    id: str
    device_model_id: str | None = None
    device_name: str | None = None
    device_model_name: str | None = None


class SupplierResponse(BaseModel):
    id: str
    name: str
    role_title: str
    phone: str | None = None
    email: str | None = None
    wechat: str | None = None
    manufacturer_id: str
    manufacturer_name: str | None = None
    notes: str | None = None
    contract_ids: list[str] = Field(default_factory=list)
    contract_nos: list[str] = Field(default_factory=list)
    products: list[SupplierProductResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
