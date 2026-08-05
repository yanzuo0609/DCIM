import api, { unwrap } from '@/api'
import type { ApiResponse } from '@/types/api'

export interface OrgChartBrief {
  id: string
  project_no: string
  name: string
  node_count: number
  created_at: string
  updated_at: string
}

export interface OrgNode {
  id: string
  chart_id: string
  parent_id: string | null
  title: string
  role_title: string | null
  person_name: string | null
  phone: string | null
  email: string | null
  pos_x: number
  pos_y: number
  sort_order: number
}

export interface OrgLink {
  id: string
  chart_id: string
  source_node_id: string
  target_node_id: string
}

export interface OrgChart {
  id: string
  project_no: string
  name: string
  canvas_json: Record<string, unknown> | unknown[] | null
  nodes: OrgNode[]
  links: OrgLink[]
  created_at: string
  updated_at: string
}

export interface InternalContact {
  id: string
  name: string
  role_title: string
  phone: string | null
  email: string | null
  company: string | null
  project_no: string | null
  org_node_id: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface SupplierProduct {
  id?: string
  device_model_id?: string | null
  device_name?: string | null
  device_model_name?: string | null
}

export interface SupplierContact {
  id: string
  name: string
  role_title: string
  phone: string | null
  email: string | null
  wechat: string | null
  manufacturer_id: string
  manufacturer_name: string | null
  notes: string | null
  contract_ids: string[]
  contract_nos: string[]
  products: SupplierProduct[]
  created_at: string
  updated_at: string
}

export async function listOrgCharts(projectNo?: string) {
  const response = await api.get<ApiResponse<OrgChartBrief[]>>('/personnel/org-charts', {
    params: projectNo ? { project_no: projectNo } : undefined,
  })
  return unwrap(response)
}

export async function getOrgChart(id: string) {
  const response = await api.get<ApiResponse<OrgChart>>(`/personnel/org-charts/${id}`)
  return unwrap(response)
}

export async function createOrgChart(payload: { project_no: string; name: string }) {
  const response = await api.post<ApiResponse<OrgChart>>('/personnel/org-charts', payload)
  return unwrap(response)
}

export async function updateOrgChart(
  id: string,
  payload: {
    name?: string
    project_no?: string
    nodes?: Array<{
      id?: string
      parent_id?: string | null
      title: string
      role_title?: string | null
      person_name?: string | null
      phone?: string | null
      email?: string | null
      pos_x?: number
      pos_y?: number
      sort_order?: number
    }>
    links?: Array<{ id?: string; source_node_id: string; target_node_id: string }>
    canvas_json?: Record<string, unknown> | null
  },
) {
  const response = await api.put<ApiResponse<OrgChart>>(`/personnel/org-charts/${id}`, payload)
  return unwrap(response)
}

export async function deleteOrgChart(id: string) {
  await api.delete(`/personnel/org-charts/${id}`)
}

export async function listInternals(params: Record<string, unknown> = {}) {
  const response = await api.get('/personnel/internals', { params })
  return response.data.data as {
    items: InternalContact[]
    pagination: { page: number; page_size: number; total: number; pages: number }
  }
}

export async function createInternal(payload: Partial<InternalContact> & { name: string }) {
  const response = await api.post<ApiResponse<InternalContact>>('/personnel/internals', payload)
  return unwrap(response)
}

export async function updateInternal(id: string, payload: Partial<InternalContact>) {
  const response = await api.put<ApiResponse<InternalContact>>(`/personnel/internals/${id}`, payload)
  return unwrap(response)
}

export async function deleteInternal(id: string) {
  await api.delete(`/personnel/internals/${id}`)
}

export async function listSuppliers(params: Record<string, unknown> = {}) {
  const response = await api.get('/personnel/suppliers', { params })
  return response.data.data as {
    items: SupplierContact[]
    pagination: { page: number; page_size: number; total: number; pages: number }
  }
}

export async function createSupplier(payload: {
  name: string
  role_title?: string
  phone?: string | null
  email?: string | null
  wechat?: string | null
  manufacturer_id: string
  notes?: string | null
  contract_ids?: string[]
  products?: SupplierProduct[]
}) {
  const response = await api.post<ApiResponse<SupplierContact>>('/personnel/suppliers', payload)
  return unwrap(response)
}

export async function updateSupplier(
  id: string,
  payload: {
    name?: string
    role_title?: string
    phone?: string | null
    email?: string | null
    wechat?: string | null
    manufacturer_id?: string
    notes?: string | null
    contract_ids?: string[]
    products?: SupplierProduct[]
  },
) {
  const response = await api.put<ApiResponse<SupplierContact>>(`/personnel/suppliers/${id}`, payload)
  return unwrap(response)
}

export async function deleteSupplier(id: string) {
  await api.delete(`/personnel/suppliers/${id}`)
}
