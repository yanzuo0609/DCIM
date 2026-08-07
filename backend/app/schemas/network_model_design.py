"""Schemas for model design (folders, models, attributes, wiring rules)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Category = Literal["server", "network", "security", "software"]


class NetworkModelFolderCreate(BaseModel):
    parent_id: uuid.UUID | None = None
    kind: Literal["folder", "project"] = "folder"
    name: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=80)
    description: str | None = None
    sort_order: int = 0


class NetworkModelFolderUpdate(BaseModel):
    parent_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=80)
    description: str | None = None
    sort_order: int | None = None


class NetworkModelFolderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_id: uuid.UUID | None
    kind: str
    name: str
    code: str | None
    description: str | None
    sort_order: int
    created_at: datetime
    updated_at: datetime


class NetworkModelFolderTreeNode(NetworkModelFolderResponse):
    children: list["NetworkModelFolderTreeNode"] = Field(default_factory=list)
    model_count: int = 0


class NetworkDesignModelCreate(BaseModel):
    folder_id: uuid.UUID
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=40)
    subtype: str = Field(min_length=1, max_length=40)
    manufacturer_name: str | None = Field(default=None, max_length=100)
    vendor_sku: str | None = Field(default=None, max_length=100)
    height_u: int = Field(default=1, ge=1, le=48)
    attributes: dict[str, Any] | None = None
    port_layout: dict[str, Any] | None = None
    device_model_id: uuid.UUID | None = None
    contract_device_name: str | None = Field(default=None, max_length=100)
    is_published: bool = True
    description: str | None = None


class NetworkDesignModelUpdate(BaseModel):
    folder_id: uuid.UUID | None = None
    code: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=40)
    subtype: str | None = Field(default=None, max_length=40)
    manufacturer_name: str | None = Field(default=None, max_length=100)
    vendor_sku: str | None = Field(default=None, max_length=100)
    height_u: int | None = Field(default=None, ge=1, le=48)
    attributes: dict[str, Any] | None = None
    port_layout: dict[str, Any] | None = None
    device_model_id: uuid.UUID | None = None
    contract_device_name: str | None = Field(default=None, max_length=100)
    is_published: bool | None = None
    description: str | None = None


class NetworkDesignModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    folder_id: uuid.UUID
    code: str
    name: str
    category: str
    subtype: str
    manufacturer_name: str | None
    vendor_sku: str | None
    height_u: int
    attributes: dict[str, Any] | None
    port_layout: dict[str, Any] | None
    device_model_id: uuid.UUID | None
    contract_device_name: str | None
    is_published: bool
    description: str | None
    created_at: datetime
    updated_at: datetime


class NetworkWiringRuleCreate(BaseModel):
    topology_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    enabled: bool = True
    mode: Literal["sequential", "manual"] = "sequential"
    config: dict[str, Any] | None = None
    description: str | None = None


class NetworkWiringRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    enabled: bool | None = None
    mode: Literal["sequential", "manual"] | None = None
    config: dict[str, Any] | None = None
    description: str | None = None


class NetworkWiringRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topology_id: uuid.UUID
    name: str
    enabled: bool
    mode: str
    config: dict[str, Any] | None
    description: str | None
    created_at: datetime
    updated_at: datetime


class TaxonomyOption(BaseModel):
    value: str
    label: str


class TaxonomyCategory(BaseModel):
    value: str
    label: str
    subtypes: list[TaxonomyOption]


class AttributeFieldDef(BaseModel):
    key: str
    label: str
    type: str  # int | float | string | bool | select | list
    required: bool = False
    min: float | None = None
    max: float | None = None
    options: list[TaxonomyOption] | None = None
    description: str | None = None


class CategoryAttributeSchema(BaseModel):
    category: str
    fields: list[AttributeFieldDef]
    default_attributes: dict[str, Any]
