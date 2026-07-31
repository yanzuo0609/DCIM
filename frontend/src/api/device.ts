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
  param_profile_id: string | null
  system_profile_id: string | null
  bmc_profile_id: string | null
  contract_id?: string | null
  contract_no?: string | null
  project_no?: string | null
  ip_summary: string | null
  bmc_ip?: string | null
  vip?: string | null
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
  /** 与上架设备按序 1:1 关联的已有 IP */
  ip_ids?: string[]
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
    ip_id?: string | null
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
  },
) {
  const response = await api.put<ApiResponse<DeviceModel>>(`/device-models/${id}`, payload)
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
  return response.data.data.items as ParamProfile[]
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
