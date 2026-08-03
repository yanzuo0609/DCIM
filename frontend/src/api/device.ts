import api, { unwrap } from '@/api'
import type { ApiResponse } from '@/types/api'

export interface Device {
  id: string
  name: string | null
  hostname: string
  serial_number: string
  device_model_id: string
  device_model_name: string | null
  manufacturer_id: string | null
  manufacturer_name: string | null
  device_type_id: string | null
  device_type_name: string | null
  device_type_code?: string | null
  param_profile_id: string | null
  system_profile_id: string | null
  bmc_profile_id: string | null
  contract_id?: string | null
  contract_no?: string | null
  project_no?: string | null
  ip_summary: string | null
  bmc_ip?: string | null
  vip?: string | null
  system_ip_id?: string | null
  bmc_ip_id?: string | null
  vip_ip_id?: string | null
  system_segment_id?: string | null
  bmc_segment_id?: string | null
  vip_segment_id?: string | null
  rack_id: string | null
  rack_code: string | null
  room_id: string | null
  room_name: string | null
  u_position: number | null
  height_u: number
  weight: number | null
  power: number | null
  status: string
  description: string | null
  /** 来自设备定义/型号的面板布局（按设备名称匹配） */
  port_layout?: Record<string, unknown> | null
  network_kind?: string | null
  panel_apply_device_name?: string | null
  /** 是否已绑定网络设备定义面板 */
  network_panel_bound?: boolean
  created_at: string
  updated_at: string
}

export interface Manufacturer {
  id: string
  code: string
  name: string
  description?: string | null
}

export interface DeviceModel {
  id: string
  code: string
  name: string
  manufacturer_id: string
  manufacturer_name: string | null
  height_u: number
  power: number | null
  description?: string | null
  port_layout?: Record<string, unknown> | null
  apply_device_name?: string | null
  network_kind?: string | null
}

export interface DeviceType {
  id: string
  code: string
  name: string
  is_system: boolean
  description: string | null
}

export interface Profile {
  id: string
  code: string
  name: string
  payload: Record<string, unknown> | unknown[] | null
  description: string | null
}

export type CpuArchitecture = 'c86' | 'arm'
export type DiskMediaType = 'ssd' | 'hdd' | 'nvme'
export type DiskRole = 'system' | 'data'

export interface ParamCpuSpec {
  cores?: number | null
  architecture?: CpuArchitecture | null
  model?: string | null
}

export interface ParamMemorySpec {
  size_gb?: number | null
  ddr_type?: string | null
  modules?: number | null
}

export interface ParamDiskSpec {
  size_gb?: number | null
  count?: number | null
  interface?: string | null
  media_type?: DiskMediaType | null
  /** system=系统盘 / data=数据盘 */
  role?: DiskRole | null
}

export interface ParamRaidSpec {
  model?: string | null
  params?: string | null
}

export interface ParamCustomField {
  key: string
  value: string
}

export interface ParamProfilePayload {
  source_device_name?: string | null
  source_device_model?: string | null
  source_manufacturer?: string | null
  device_type_id?: string | null
  /** 详细参数（可自由编辑的文本） */
  detail_params?: string | null
  /** 其他参数：风扇/电源/RAID/操作系统等合并文本 */
  other_params?: string | null
  cpu?: ParamCpuSpec | null
  memory?: ParamMemorySpec | null
  disks?: ParamDiskSpec[]
  fan_count?: number | null
  fan_model?: string | null
  psu_power_w?: number | null
  raid?: ParamRaidSpec | null
  supported_os?: string[]
  custom?: ParamCustomField[]
}

export interface ParamProfile {
  id: string
  code: string
  name: string
  payload: ParamProfilePayload | null
  description: string | null
  summary?: string | null
  is_complete?: boolean
  missing_fields?: string[]
  source_device_name?: string | null
  source_device_model?: string | null
  source_manufacturer?: string | null
  device_type_id?: string | null
  detail_params?: string | null
  other_params?: string | null
}

export interface ParamProfileSyncResult {
  created: number
  updated: number
  skipped: number
  total_summary: number
  messages: string[]
}

export interface ParamProfileImportResult {
  updated: number
  created: number
  skipped: number
  errors: string[]
}

export type CredentialRole = 'admin' | 'readonly' | 'operator' | 'custom'
export type OsType = 'linux' | 'windows' | 'unix' | 'esxi' | 'other'

export const MASKED_PASSWORD = '********'

export interface CredentialAccount {
  username: string
  password?: string | null
  role?: CredentialRole
  note?: string | null
  password_set?: boolean | null
}

export interface BmcProfilePayload {
  users?: CredentialAccount[]
}

export interface SystemProfilePayload {
  os_type?: OsType | null
  os_name?: string | null
  users?: CredentialAccount[]
  custom_users?: CredentialAccount[]
}

export interface BmcProfile {
  id: string
  code: string
  name: string
  payload: BmcProfilePayload | null
  description: string | null
  summary?: string | null
}

export interface SystemProfile {
  id: string
  code: string
  name: string
  payload: SystemProfilePayload | null
  description: string | null
  summary?: string | null
}

export interface DevicePayload {
  name?: string | null
  hostname?: string | null
  serial_number: string
  device_model_id: string
  device_type_id?: string | null
  param_profile_id?: string | null
  system_profile_id?: string | null
  bmc_profile_id?: string | null
  contract_id?: string | null
  height_u?: number | null
  weight?: number | null
  power?: number | null
  status?: string | null
  description?: string | null
  system_ip_id?: string | null
  bmc_ip_id?: string | null
  vip_ip_id?: string | null
}

export interface BatchMountNewDevice {
  name?: string | null
  hostname?: string | null
  serial_number: string
  device_model_id: string
  device_type_id?: string | null
  height_u?: number | null
  power?: number | null
  description?: string | null
  contract_id?: string | null
}

export interface BatchMountPayload {
  room_id: string
  device_ids?: string[]
  new_devices?: BatchMountNewDevice[]
  rack_ids?: string[]
  row_nos?: number[]
  column_nos?: number[]
  per_rack_count?: number
  /** 每柜上架起始 U，默认 1 */
  start_u?: number
  /** 设备间空闲 U 间隔，默认 1 */
  gap_u?: number
  /** 业务 IP，与上架设备按序 1:1 关联 */
  ip_ids?: string[]
  /** BMC/带外 IP，与上架设备按序 1:1 关联 */
  bmc_ip_ids?: string[]
}

export interface BatchMountResult {
  mounted: number
  created: number
  ip_bound: number
  skipped: number
  errors: string[]
  assignments: Array<{
    device_id: string
    hostname: string
    rack_id: string
    rack_code: string
    u_position: number
    system_ip?: string | null
    bmc_ip?: string | null
    ip_id?: string | null
    bmc_ip_id?: string | null
  }>
}

export interface BatchUnmountResult {
  unmounted: number
  skipped: number
  errors: string[]
}

export interface BatchDeleteResult {
  deleted: number
  skipped: number
  errors: string[]
}

export async function listDevices(params: Record<string, unknown> = {}) {
  const response = await api.get('/devices', { params })
  return response.data.data
}

export async function getDevice(id: string): Promise<Device> {
  const response = await api.get<ApiResponse<Device>>(`/devices/${id}`)
  return unwrap(response)
}

export async function listManufacturers(params: Record<string, unknown> = {}) {
  const response = await api.get('/manufacturers', { params: { page_size: 100, ...params } })
  return response.data.data.items as Manufacturer[]
}

export async function createManufacturer(payload: {
  code: string
  name: string
  description?: string | null
}) {
  const response = await api.post<ApiResponse<Manufacturer>>('/manufacturers', payload)
  return unwrap(response)
}

export async function listDeviceModels() {
  const response = await api.get('/device-models', { params: { page_size: 100 } })
  return response.data.data.items as DeviceModel[]
}

export async function createDeviceModel(payload: {
  code: string
  name: string
  manufacturer_id?: string | null
  height_u?: number
  power?: number | null
  description?: string | null
}) {
  const response = await api.post<ApiResponse<DeviceModel>>('/device-models', payload)
  return unwrap(response)
}

export async function updateDeviceModel(
  id: string,
  payload: {
    code?: string
    name?: string
    height_u?: number
    power?: number | null
    description?: string | null
    port_layout?: Record<string, unknown> | null
    apply_device_name?: string | null
    network_kind?: string | null
  },
) {
  const response = await api.put<ApiResponse<DeviceModel>>(`/device-models/${id}`, payload)
  return unwrap(response)
}

export async function applyDeviceModelPanel(
  modelId: string,
  payload: {
    port_layout: Record<string, unknown>
    apply_device_name: string
    network_kind?: string | null
    mode?: 'apply' | 'modify'
    device_ids?: string[]
  },
) {
  const response = await api.post<
    ApiResponse<{
      device_model_id: string
      apply_device_name: string
      mode: string
      matched_device_count: number
      matched_device_ids: string[]
      applied_count: number
      modified_count: number
      skipped_count: number
      skipped_device_ids: string[]
      message?: string | null
    }>
  >(`/device-models/${modelId}/apply-panel`, payload)
  return unwrap(response)
}

export interface DevicePanelCandidate {
  id: string
  name: string | null
  hostname: string
  serial_number: string
  device_model_id: string
  device_model_name: string | null
  network_panel_bound: boolean
  rack_code: string | null
  room_name: string | null
  u_position: number | null
  status: string
}

export async function listPanelCandidates(modelId: string, applyDeviceName: string) {
  const response = await api.get<
    ApiResponse<{
      apply_device_name: string
      items: DevicePanelCandidate[]
      unbound_count: number
      bound_count: number
    }>
  >(`/device-models/${modelId}/panel-candidates`, {
    params: { apply_device_name: applyDeviceName },
  })
  return unwrap(response)
}

export async function deleteDeviceModel(id: string) {
  await api.delete(`/device-models/${id}`)
}

export async function listDeviceTypes() {
  const response = await api.get('/device-types', { params: { page_size: 100 } })
  return response.data.data.items as DeviceType[]
}

export async function createDeviceType(payload: { code: string; name: string; description?: string | null }) {
  const response = await api.post<ApiResponse<DeviceType>>('/device-types', payload)
  return unwrap(response)
}

export async function updateDeviceType(
  id: string,
  payload: { code?: string; name?: string; description?: string | null },
) {
  const response = await api.put<ApiResponse<DeviceType>>(`/device-types/${id}`, payload)
  return unwrap(response)
}

export async function deleteDeviceType(id: string) {
  await api.delete(`/device-types/${id}`)
}

export async function listParamProfiles() {
  const response = await api.get('/device-param-profiles', { params: { page_size: 100 } })
  const data = response.data?.data
  const items = data?.items
  if (!Array.isArray(items)) {
    throw new Error('设备参数列表响应格式异常')
  }
  return items as ParamProfile[]
}

function makeParamCode(deviceName: string): string {
  let hash = 0
  const text = deviceName || 'device'
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash << 5) - hash + text.charCodeAt(i)
    hash |= 0
  }
  const digest = Math.abs(hash).toString(16).padStart(8, '0').slice(0, 8)
  const ascii = text
    .normalize('NFKD')
    .replace(/[^\x00-\x7F]/g, '')
    .replace(/[^A-Za-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
  const slug = ascii || 'dev'
  return `P-${slug.slice(0, 24)}-${digest}`.slice(0, 50)
}

/**
 * 按采购汇总「设备名称」同步空待填参数：
 * - 不存在同名 → 新建空表（待完善）
 * - 已存在同名 → 跳过
 * 直接走前端编排（采购汇总 + 创建），避免专用接口异常导致整页失败。
 */
export async function syncParamProfilesFromContracts(): Promise<ParamProfileSyncResult> {
  const { getContractSummary } = await import('@/api/contract')
  const [summary, profiles] = await Promise.all([getContractSummary(), listParamProfiles()])
  const existing = new Set(
    profiles
      .map((p) => (p.source_device_name || p.name || '').trim().toLowerCase())
      .filter(Boolean),
  )
  const uniqueNames = new Map<string, string>()
  for (const row of summary || []) {
    const name = (row.device_name || '').trim().slice(0, 100)
    if (!name) continue
    const key = name.toLowerCase()
    if (!uniqueNames.has(key)) uniqueNames.set(key, name)
  }

  let created = 0
  let skipped = 0
  const messages: string[] = []
  const usedCodes = new Set(profiles.map((p) => p.code))

  for (const [key, deviceName] of uniqueNames) {
    if (existing.has(key)) {
      skipped += 1
      continue
    }
    let code = makeParamCode(deviceName)
    let n = 1
    while (usedCodes.has(code)) {
      code = `${makeParamCode(deviceName).slice(0, 40)}-${n}`.slice(0, 50)
      n += 1
    }
    await createParamProfile({
      code,
      name: deviceName,
      description: '待完善：由采购汇总设备名称同步生成',
      payload: {
        source_device_name: deviceName,
        disks: [{ role: 'system' }, { role: 'data' }, { role: 'data' }],
      },
    })
    usedCodes.add(code)
    existing.add(key)
    created += 1
    messages.push(`已新建待完善项：${deviceName}`)
  }

  return {
    created,
    updated: 0,
    skipped,
    total_summary: uniqueNames.size,
    messages: messages.slice(0, 50),
  }
}

export async function downloadParamProfilesTemplate() {
  await downloadBlob(
    '/device-param-profiles/import/template',
    'device_param_profiles_template.xlsx',
  )
}

export async function exportParamProfiles(incompleteOnly = false) {
  const qs = incompleteOnly ? '?incomplete_only=true' : ''
  const filename = incompleteOnly
    ? 'device_param_profiles_incomplete.xlsx'
    : 'device_param_profiles.xlsx'
  await downloadBlob(`/device-param-profiles/export${qs}`, filename)
}

export async function importParamProfiles(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post<ApiResponse<ParamProfileImportResult>>(
    '/device-param-profiles/import',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  )
  return unwrap(response)
}

export async function createParamProfile(payload: {
  code: string
  name: string
  payload?: ParamProfilePayload | null
  description?: string | null
}) {
  const response = await api.post<ApiResponse<ParamProfile>>('/device-param-profiles', payload)
  return unwrap(response)
}

export async function updateParamProfile(
  id: string,
  payload: { name?: string; payload?: ParamProfilePayload | null; description?: string | null },
) {
  const response = await api.put<ApiResponse<ParamProfile>>(`/device-param-profiles/${id}`, payload)
  return unwrap(response)
}

export async function deleteParamProfile(id: string) {
  await api.delete(`/device-param-profiles/${id}`)
}

export async function listSystemProfiles() {
  const response = await api.get('/device-system-profiles', { params: { page_size: 100 } })
  return response.data.data.items as SystemProfile[]
}

export async function createSystemProfile(payload: {
  code: string
  name: string
  payload?: SystemProfilePayload | null
  description?: string | null
}) {
  const response = await api.post<ApiResponse<SystemProfile>>('/device-system-profiles', payload)
  return unwrap(response)
}

export async function updateSystemProfile(
  id: string,
  payload: { name?: string; payload?: SystemProfilePayload | null; description?: string | null },
) {
  const response = await api.put<ApiResponse<SystemProfile>>(`/device-system-profiles/${id}`, payload)
  return unwrap(response)
}

export async function deleteSystemProfile(id: string) {
  await api.delete(`/device-system-profiles/${id}`)
}

export async function listBmcProfiles() {
  const response = await api.get('/device-bmc-profiles', { params: { page_size: 100 } })
  return response.data.data.items as BmcProfile[]
}

export async function createBmcProfile(payload: {
  code: string
  name: string
  payload?: BmcProfilePayload | null
  description?: string | null
}) {
  const response = await api.post<ApiResponse<BmcProfile>>('/device-bmc-profiles', payload)
  return unwrap(response)
}

export async function updateBmcProfile(
  id: string,
  payload: { name?: string; payload?: BmcProfilePayload | null; description?: string | null },
) {
  const response = await api.put<ApiResponse<BmcProfile>>(`/device-bmc-profiles/${id}`, payload)
  return unwrap(response)
}

export async function deleteBmcProfile(id: string) {
  await api.delete(`/device-bmc-profiles/${id}`)
}

export async function createDevice(payload: DevicePayload): Promise<Device> {
  const response = await api.post<ApiResponse<Device>>('/devices', payload)
  return unwrap(response)
}

export async function updateDevice(id: string, payload: DevicePayload): Promise<Device> {
  const response = await api.put<ApiResponse<Device>>(`/devices/${id}`, payload)
  return unwrap(response)
}

export async function deleteDevice(id: string): Promise<void> {
  await api.delete(`/devices/${id}`)
}

export async function batchDeleteDevices(ids: string[]): Promise<BatchDeleteResult> {
  const response = await api.post<ApiResponse<BatchDeleteResult>>('/devices/batch-delete', { ids })
  return unwrap(response)
}

export async function mountDevice(rackId: string, deviceId: string, uPosition: number) {
  const response = await api.post<ApiResponse<{ valid: boolean; message: string }>>('/layout/mount', {
    device_id: deviceId,
    rack_id: rackId,
    u_position: uPosition,
  })
  return unwrap(response)
}

export async function unmountDevice(deviceId: string) {
  const response = await api.post<ApiResponse<{ valid: boolean; message: string }>>('/layout/unmount', {
    device_id: deviceId,
  })
  return unwrap(response)
}

export async function batchMountDevices(payload: BatchMountPayload): Promise<BatchMountResult> {
  const response = await api.post<ApiResponse<BatchMountResult>>('/layout/batch-mount', payload)
  return unwrap(response)
}

export async function batchUnmountDevices(ids: string[]): Promise<BatchUnmountResult> {
  const response = await api.post<ApiResponse<BatchUnmountResult>>('/layout/batch-unmount', {
    device_ids: ids,
  })
  return unwrap(response)
}

export async function autoLayout(rackId: string, deviceId: string) {
  const response = await api.post<ApiResponse<{ u_position: number | null; message: string }>>(
    '/layout/auto',
    { rack_id: rackId, device_id: deviceId },
  )
  return unwrap(response)
}

export interface ImportResult {
  created: number
  failed: number
  errors: string[]
}

async function downloadBlob(path: string, filename: string) {
  const response = await api.get(path, { responseType: 'blob' })
  const url = window.URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  window.URL.revokeObjectURL(url)
}

export async function exportDevicesExcel() {
  await downloadBlob('/devices/export?format=xlsx', 'devices.xlsx')
}

export async function exportDevicesPdf() {
  await downloadBlob('/devices/export?format=pdf', 'devices.pdf')
}

export async function downloadImportTemplate() {
  await downloadBlob('/devices/import/template', 'device_import_template.xlsx')
}

export async function importDevices(file: File): Promise<ImportResult> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post<ApiResponse<ImportResult>>('/devices/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return unwrap(response)
}
