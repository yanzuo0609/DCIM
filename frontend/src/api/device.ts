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
  project_scope?: string | null
  project_app?: string | null
  warranty_years?: number | null
  mounted_at?: string | null
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
export type DiskRole = 'system' | 'cache' | 'data'

export interface ParamCpuSpec {
  model?: string | null
  count?: number | null
  cores?: number | null
  architecture?: CpuArchitecture | null
}

export interface ParamMemorySpec {
  ddr_type?: string | null
  stick_size_gb?: number | null
  size_gb?: number | null
  modules?: number | null
}

export interface ParamDiskSpec {
  size_gb?: number | null
  count?: number | null
  interface?: string | null
  media_type?: DiskMediaType | null
  /** system=系统盘 / cache=缓存盘 / data=数据盘 */
  role?: DiskRole | null
}

export interface ParamRaidSpec {
  model?: string | null
  params?: string | null
}

export interface ParamNicSpec {
  ge_nic_count?: number | null
  ge_port_count?: number | null
  xe_nic_count?: number | null
  xe_port_count?: number | null
  onboard_type?: string | null
  onboard_count?: number | null
  pcie_slot_count?: number | null
}

export interface ParamGpuSpec {
  model?: string | null
  count?: number | null
  vram_gb?: number | null
  bandwidth?: string | null
}

export interface ParamSwitchSpec {
  switching_capacity?: string | null
  forwarding_rate?: string | null
  service_card_count?: number | null
  fabric_card_count?: number | null
  /** 接口卡数量 */
  interface_card_count?: number | null
  /** 接口卡类型：400G/100G/40G/25G/10G/1G */
  interface_card_type?: string | null
  /** DOWNLINK接口个数 */
  downlink_port_count?: number | null
  /** UPLINK上联接口类型：400G/100G/40G/25G/10G */
  uplink_port_type?: string | null
  /** UPLINK上联接口个数 */
  uplink_port_count?: number | null
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
  detail_params?: string | null
  other_params?: string | null
  cpu?: ParamCpuSpec | null
  memory?: ParamMemorySpec | null
  disks?: ParamDiskSpec[]
  nic?: ParamNicSpec | null
  gpu?: ParamGpuSpec | null
  switch?: ParamSwitchSpec | null
  height_u?: number | null
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
  manufacturer_id?: string | null
  param_profile_id?: string | null
  system_profile_id?: string | null
  bmc_profile_id?: string | null
  contract_id?: string | null
  height_u?: number | null
  weight?: number | null
  power?: number | null
  status?: string | null
  description?: string | null
  project_scope?: string | null
  project_app?: string | null
  warranty_years?: number | null
  mounted_at?: string | null
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
  manufacturer_id?: string | null
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
  /** 已创建但因无可用 U 位而未上架、保留在库存 */
  stock_only?: number
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

export interface DeviceBatchUpdateFields {
  name?: string | null
  device_type_id?: string | null
  device_model_id?: string | null
  height_u?: number | null
  manufacturer_id?: string | null
  contract_id?: string | null
  system_ip_id?: string | null
  bmc_ip_id?: string | null
  vip_ip_id?: string | null
}

export interface DeviceBatchMountSpec {
  rack_id: string
  start_u?: number
  gap_u?: number
}

export interface DeviceBatchUpdatePayload {
  ids: string[]
  fields?: DeviceBatchUpdateFields
  system_ip_ids?: string[]
  bmc_ip_ids?: string[]
  vip_ip_id?: string | null
  unmount?: boolean
  mount?: DeviceBatchMountSpec
}

export interface DeviceBatchUpdateResult {
  updated: number
  unmounted: number
  mounted: number
  skipped: number
  errors: string[]
}

export async function listDevices(params: Record<string, unknown> = {}) {
  const response = await api.get('/devices', { params })
  return response.data.data
}

export interface DeviceBatchNextIndex {
  start_index: number
  hostname_max: number
  serial_max: number
  hostname_prefix: string
  serial_prefix: string
}

/** 按主机名/序列号前缀建议批量新建起始序号 */
export async function suggestBatchStartIndex(params: {
  hostname_prefix?: string
  serial_prefix?: string
}): Promise<DeviceBatchNextIndex> {
  const response = await api.get<ApiResponse<DeviceBatchNextIndex>>('/devices/next-batch-index', {
    params,
  })
  return unwrap(response)
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
    manufacturer_id?: string | null
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

export async function listParamProfiles(params: Record<string, unknown> = {}) {
  const response = await api.get('/device-param-profiles', {
    params: { page_size: 200, ...params },
  })
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
 * 按资产汇总「设备名称」与资产详细参数双向关联同步：
 * - 汇总有、参数无 → 新建空待完善参数（名称 / 产品型号 / 产品厂商对齐）
 * - 同名已存在 → 校正设备名称，并以汇总为准同步产品型号、产品厂商
 * - 参数有、汇总无 → 保留（不删除）
 */
export async function syncParamProfilesFromContracts(): Promise<ParamProfileSyncResult> {
  const { getContractSummary } = await import('@/api/contract')
  const [summary, profiles] = await Promise.all([getContractSummary(), listParamProfiles()])

  type SummaryMeta = {
    name: string
    model: string
    manufacturer: string
  }
  const uniqueNames = new Map<string, SummaryMeta>()
  for (const row of summary || []) {
    const name = (row.device_name || '').trim().slice(0, 100)
    if (!name) continue
    const key = name.toLowerCase()
    const model = (row.device_model_name || '').trim()
    const manufacturer = (row.manufacturer_name || '').trim()
    const prev = uniqueNames.get(key)
    if (!prev) {
      uniqueNames.set(key, { name, model, manufacturer })
      continue
    }
    if (!prev.model && model) prev.model = model
    if (!prev.manufacturer && manufacturer) prev.manufacturer = manufacturer
  }

  const profileByKey = new Map<string, ParamProfile>()
  for (const p of profiles) {
    const keys = [
      (p.source_device_name || '').trim().toLowerCase(),
      (p.payload?.source_device_name || '').trim().toLowerCase(),
      (p.name || '').trim().toLowerCase(),
    ].filter(Boolean)
    for (const key of keys) {
      if (!profileByKey.has(key)) profileByKey.set(key, p)
    }
  }

  let created = 0
  let updated = 0
  let skipped = 0
  const messages: string[] = []
  const usedCodes = new Set(profiles.map((p) => p.code))
  const touched = new Set<string>()

  for (const [key, meta] of uniqueNames) {
    const existed = profileByKey.get(key)
    if (!existed) {
      let code = makeParamCode(meta.name)
      let n = 1
      while (usedCodes.has(code)) {
        code = `${makeParamCode(meta.name).slice(0, 40)}-${n}`.slice(0, 50)
        n += 1
      }
      const createdRow = await createParamProfile({
        code,
        name: meta.name,
        description: '待完善：由采购汇总设备名称同步生成',
        payload: {
          source_device_name: meta.name,
          source_device_model: meta.model || null,
          source_manufacturer: meta.manufacturer || null,
          disks: [{ role: 'system' }, { role: 'data' }, { role: 'data' }],
        },
      })
      usedCodes.add(code)
      profileByKey.set(key, createdRow)
      created += 1
      messages.push(`已新建待完善项：${meta.name}`)
      continue
    }

    if (touched.has(existed.id)) {
      skipped += 1
      continue
    }
    touched.add(existed.id)

    const payload: ParamProfilePayload = { ...(existed.payload || {}) }
    let changed = false
    if ((existed.name || '').trim() !== meta.name) changed = true
    if ((payload.source_device_name || '').trim() !== meta.name) {
      payload.source_device_name = meta.name
      changed = true
    }
    // 以资产汇总为准：有值则对齐产品型号 / 产品厂商
    if (meta.model && (payload.source_device_model || '').trim() !== meta.model) {
      payload.source_device_model = meta.model
      changed = true
    }
    if (meta.manufacturer && (payload.source_manufacturer || '').trim() !== meta.manufacturer) {
      payload.source_manufacturer = meta.manufacturer
      changed = true
    }

    if (!changed) {
      skipped += 1
      continue
    }

    await updateParamProfile(existed.id, {
      name: meta.name,
      payload,
    })
    updated += 1
    messages.push(`已关联同步：${meta.name}`)
  }

  return {
    created,
    updated,
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
  payload: {
    code?: string
    name?: string
    payload?: ParamProfilePayload | null
    description?: string | null
  },
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

export async function batchUpdateDevices(
  payload: DeviceBatchUpdatePayload,
): Promise<DeviceBatchUpdateResult> {
  const response = await api.post<ApiResponse<DeviceBatchUpdateResult>>(
    '/devices/batch-update',
    payload,
  )
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
