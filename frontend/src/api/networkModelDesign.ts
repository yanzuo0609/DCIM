import api, { unwrap } from '@/api'
import type { ApiResponse, PaginatedResponse } from '@/types/api'
import type { PortLayout } from '@/api/network'

export type ModelCategory = 'server' | 'network' | 'security' | 'software'
export type FolderKind = 'folder' | 'project'
export type WiringMode = 'sequential' | 'manual'

export interface TaxonomyOption {
  value: string
  label: string
}

export interface TaxonomyCategory {
  value: ModelCategory | string
  label: string
  subtypes: TaxonomyOption[]
}

export interface AttributeFieldDef {
  key: string
  label: string
  type: string
  required?: boolean
  min?: number | null
  max?: number | null
  options?: TaxonomyOption[] | null
  description?: string | null
}

export interface CategoryAttributeSchema {
  category: string
  fields: AttributeFieldDef[]
  default_attributes: Record<string, unknown>
}

export interface NetworkModelFolder {
  id: string
  parent_id: string | null
  kind: FolderKind | string
  name: string
  code: string | null
  description: string | null
  sort_order: number
  created_at: string
  updated_at: string
}

export interface NetworkModelFolderTreeNode extends NetworkModelFolder {
  children: NetworkModelFolderTreeNode[]
  model_count: number
}

export interface NetworkDesignModel {
  id: string
  folder_id: string
  code: string
  name: string
  category: string
  subtype: string
  manufacturer_name: string | null
  vendor_sku: string | null
  height_u: number
  attributes: Record<string, unknown> | null
  port_layout: PortLayout | null
  device_model_id: string | null
  contract_device_name: string | null
  is_published: boolean
  description: string | null
  created_at: string
  updated_at: string
}

export interface NetworkDesignModelCreate {
  folder_id: string
  code: string
  name: string
  category: string
  subtype: string
  manufacturer_name?: string | null
  vendor_sku?: string | null
  height_u?: number
  attributes?: Record<string, unknown> | null
  port_layout?: PortLayout | null
  device_model_id?: string | null
  contract_device_name?: string | null
  is_published?: boolean
  description?: string | null
}

export type NetworkDesignModelUpdate = Partial<NetworkDesignModelCreate>

export interface NetworkWiringRule {
  id: string
  project_id?: string | null
  topology_id?: string | null
  name: string
  enabled: boolean
  mode: WiringMode | string
  config: Record<string, unknown> | null
  description: string | null
  created_at: string
  updated_at: string
}

export interface NetworkWiringRuleCreate {
  project_id?: string | null
  topology_id?: string | null
  name: string
  enabled?: boolean
  mode?: WiringMode
  config?: Record<string, unknown> | null
  description?: string | null
}

export type NetworkWiringRuleUpdate = Partial<
  Omit<NetworkWiringRuleCreate, 'topology_id' | 'project_id'>
>
export async function fetchModelTaxonomy() {
  const response = await api.get<ApiResponse<TaxonomyCategory[]>>('/network-model-design/taxonomy')
  return unwrap(response) || []
}

export async function fetchAttributeSchema(category: string, subtype?: string) {
  const response = await api.get<ApiResponse<CategoryAttributeSchema>>(
    `/network-model-design/attribute-schema/${category}`,
    { params: subtype ? { subtype } : undefined },
  )
  return unwrap(response)
}

export async function fetchFolderTree() {
  const response = await api.get<ApiResponse<NetworkModelFolderTreeNode[]>>(
    '/network-model-design/folders/tree',
  )
  return unwrap(response) || []
}

export async function createFolder(payload: {
  parent_id?: string | null
  kind: FolderKind
  name: string
  code?: string | null
  description?: string | null
  sort_order?: number
}) {
  const response = await api.post<ApiResponse<NetworkModelFolder>>(
    '/network-model-design/folders',
    payload,
  )
  return unwrap(response)
}

export async function updateFolder(
  id: string,
  payload: Partial<{
    parent_id: string | null
    name: string
    code: string | null
    description: string | null
    sort_order: number
  }>,
) {
  const response = await api.put<ApiResponse<NetworkModelFolder>>(
    `/network-model-design/folders/${id}`,
    payload,
  )
  return unwrap(response)
}

export async function deleteFolder(id: string) {
  const response = await api.delete<ApiResponse<{ message: string }>>(
    `/network-model-design/folders/${id}`,
  )
  return unwrap(response)
}

export async function listDesignModels(params?: {
  page?: number
  page_size?: number
  keyword?: string
  folder_id?: string
  category?: string
  subtype?: string
  published_only?: boolean
  include_descendants?: boolean
}) {
  const response = await api.get<PaginatedResponse<NetworkDesignModel>>(
    '/network-model-design/models',
    { params },
  )
  return response.data.data
}

export async function getDesignModel(id: string) {
  const response = await api.get<ApiResponse<NetworkDesignModel>>(
    `/network-model-design/models/${id}`,
  )
  return unwrap(response)
}

export async function createDesignModel(payload: NetworkDesignModelCreate) {
  const response = await api.post<ApiResponse<NetworkDesignModel>>(
    '/network-model-design/models',
    payload,
  )
  return unwrap(response)
}

export async function updateDesignModel(id: string, payload: NetworkDesignModelUpdate) {
  const response = await api.put<ApiResponse<NetworkDesignModel>>(
    `/network-model-design/models/${id}`,
    payload,
  )
  return unwrap(response)
}

export async function deleteDesignModel(id: string) {
  const response = await api.delete<ApiResponse<{ message: string }>>(
    `/network-model-design/models/${id}`,
  )
  return unwrap(response)
}

export async function listWiringRules(opts?: {
  projectId?: string | null
  topologyId?: string | null
}) {
  const params: Record<string, string> = {}
  // 兼容旧调用；后端已改为返回全局规则，忽略过滤
  if (opts?.projectId) params.project_id = opts.projectId
  if (opts?.topologyId) params.topology_id = opts.topologyId
  const response = await api.get<ApiResponse<NetworkWiringRule[]>>(
    '/network-model-design/wiring-rules',
    { params },
  )
  return unwrap(response) || []
}

export async function createWiringRule(payload: NetworkWiringRuleCreate) {
  const response = await api.post<ApiResponse<NetworkWiringRule>>(
    '/network-model-design/wiring-rules',
    payload,
  )
  return unwrap(response)
}

export async function updateWiringRule(id: string, payload: NetworkWiringRuleUpdate) {
  const response = await api.put<ApiResponse<NetworkWiringRule>>(
    `/network-model-design/wiring-rules/${id}`,
    payload,
  )
  return unwrap(response)
}

export async function deleteWiringRule(id: string) {
  const response = await api.delete<ApiResponse<{ message: string }>>(
    `/network-model-design/wiring-rules/${id}`,
  )
  return unwrap(response)
}
