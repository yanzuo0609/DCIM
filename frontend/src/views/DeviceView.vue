<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  batchDeleteDevices,
  batchMountDevices,
  batchUnmountDevices,
  createBmcProfile,
  createDevice,
  createDeviceModel,
  createDeviceType,
  createManufacturer,
  createParamProfile,
  createSystemProfile,
  deleteBmcProfile,
  deleteDevice,
  deleteDeviceModel,
  deleteDeviceType,
  deleteParamProfile,
  deleteSystemProfile,
  exportDevicesExcel,
  exportDevicesPdf,
  getDevice,
  importDevices,
  listBmcProfiles,
  listDeviceModels,
  listDeviceTypes,
  listManufacturers,
  listDevices,
  listParamProfiles,
  listSystemProfiles,
  MASKED_PASSWORD,
  mountDevice,
  unmountDevice,
  updateBmcProfile,
  updateDevice,
  updateDeviceModel,
  updateDeviceType,
  updateParamProfile,
  updateSystemProfile,
  type BatchMountNewDevice,
  type BmcProfile,
  type BmcProfilePayload,
  type CredentialAccount,
  type CredentialRole,
  type Device,
  type DeviceModel,
  type DeviceType,
  type Manufacturer,
  type OsType,
  type ParamCustomField,
  type ParamDiskSpec,
  type ParamProfile,
  type ParamProfilePayload,
  type SystemProfile,
  type SystemProfilePayload,
} from '@/api/device'
import {
  allocateIpAddresses,
  batchBindIpAddresses,
  batchCreateIpAddresses,
  batchDeleteIpAddresses,
  batchSetIpStatus,
  bindIpAddress,
  createIpAddress,
  deleteIpAddress,
  listIpAddresses,
  updateIpAddress,
  type IpAddress,
  type IpBindType,
  type IpStatus,
} from '@/api/ip'
import {
  listDeviceContracts,
  normalizeContractItems,
  type DeviceContract,
} from '@/api/contract'
import { getRackLayout, listRacks, type Rack, type RackLayoutSlot } from '@/api/rack'
import { listRooms, type Room } from '@/api/room'
import BatchCreateDeviceDialog from '@/components/BatchCreateDeviceDialog.vue'
import RackCabinet from '@/components/RackCabinet.vue'
import RackRangePicker from '@/components/RackRangePicker.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const activeTab = ref<'devices' | 'profiles' | 'ips'>('devices')
const profileSubTab = ref<'param' | 'bmc' | 'system' | 'type' | 'model'>('param')

const loading = ref(false)
const tableData = ref<Device[]>([])
const selectedDevices = ref<Device[]>([])
const models = ref<DeviceModel[]>([])
const types = ref<DeviceType[]>([])
const rooms = ref<Room[]>([])
const racks = ref<Rack[]>([])
const paramProfiles = ref<ParamProfile[]>([])
const bmcProfiles = ref<BmcProfile[]>([])
const systemProfiles = ref<SystemProfile[]>([])
const contracts = ref<DeviceContract[]>([])
const manufacturers = ref<Manufacturer[]>([])
const syncModelsLoading = ref(false)
const formContracts = computed(() => contracts.value)

const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const keyword = ref('')

const ipLoading = ref(false)
const ipTableData = ref<IpAddress[]>([])
const selectedIps = ref<IpAddress[]>([])
const ipPagination = reactive({ page: 1, page_size: 20, total: 0 })
const ipKeyword = ref('')
const ipStatusFilter = ref<IpStatus | ''>('')
const ipBatchBusy = ref(false)

const IP_STATUS_OPTIONS: Array<{ value: IpStatus; label: string; type: 'success' | 'warning' | 'info' | 'danger' }> = [
  { value: 'free', label: '空闲', type: 'success' },
  { value: 'allocated', label: '已分配', type: 'warning' },
  { value: 'disabled', label: '已禁用', type: 'info' },
]

function ipStatusMeta(status: string | undefined | null) {
  return IP_STATUS_OPTIONS.find((o) => o.value === status) || { value: 'free' as IpStatus, label: status || '空闲', type: 'success' as const }
}

function ipStatusLabel(status: string | undefined | null) {
  return ipStatusMeta(status).label
}
const bindDeviceOptions = ref<Device[]>([])

const ipDialogVisible = ref(false)
const ipEditingId = ref<string | null>(null)
const ipForm = reactive({
  system_ip: '',
  bmc_ip: '',
  vip: '',
  netmask: '',
  gateway: '',
  dns: '',
  dns_secondary: '',
  label: '',
  description: '',
})

const ipBatchCreateVisible = ref(false)
const ipBatchForm = reactive({
  start_system_ip: '',
  end_system_ip: '',
  start_bmc_ip: '',
  netmask: '255.255.255.0',
  gateway: '',
  dns: '',
  dns_secondary: '',
  label_prefix: '',
})

const ipBindVisible = ref(false)
const ipBindMode = ref<'batch' | 'single'>('batch')
const ipBindTargetId = ref<string | null>(null)
const ipBindForm = reactive({
  bind_type: 'device' as IpBindType,
  device_id: '',
  room_id: '',
  rack_id: '',
  rack_ids: [] as string[],
  u_position: null as number | null,
})
const ipBindLayoutLoading = ref(false)
const ipBindLayoutSlots = ref<RackLayoutSlot[]>([])
const ipBindLayoutCode = ref('')

const ipAllocateVisible = ref(false)
const ipAllocateForm = reactive({
  room_id: '',
  rack_ids: [] as string[],
})

const editVisible = ref(false)
const editingId = ref<string | null>(null)
const form = reactive({
  name: '',
  hostname: '',
  serial_number: '',
  device_model_id: '',
  device_type_id: '' as string | null,
  param_profile_id: '' as string | null,
  bmc_profile_id: '' as string | null,
  system_profile_id: '' as string | null,
  contract_id: '' as string | null,
  height_u: 1 as number | null,
  power: null as number | null,
  description: '',
  room_id: '',
  rack_id: '',
  u_position: 1 as number | null,
})

const originalMount = ref<{ rack_id: string | null; u_position: number | null }>({
  rack_id: null,
  u_position: null,
})

const formRacks = computed(() =>
  racks.value.filter((r) => !form.room_id || r.room_id === form.room_id),
)

const formRackMeta = computed(() => racks.value.find((r) => r.id === form.rack_id) || null)

const formLayoutLoading = ref(false)
const formLayoutSlots = ref<RackLayoutSlot[]>([])
const formLayoutTotalPower = ref(0)

const mountVisible = ref(false)
const mountForm = reactive({
  device_id: '',
  room_id: '',
  rack_id: '',
  u_position: 1,
})
const mountRacks = computed(() =>
  racks.value.filter((r) => !mountForm.room_id || r.room_id === mountForm.room_id),
)
const mountRackMeta = computed(() => racks.value.find((r) => r.id === mountForm.rack_id) || null)
const mountLayoutLoading = ref(false)
const mountLayoutSlots = ref<RackLayoutSlot[]>([])
const mountLayoutTotalPower = ref(0)
const mountLayoutCode = ref('')

const rackDetailVisible = ref(false)
const rackDetailLoading = ref(false)
const rackDetailRack = ref<Rack | null>(null)
const rackDetailSlots = ref<RackLayoutSlot[]>([])
const rackDetailPower = ref(0)
const rackDetailDeviceId = ref<string | null>(null)

const batchCreateVisible = ref(false)

const wizardVisible = ref(false)
const wizardStep = ref(0)
const wizardSource = ref<'stock' | 'create'>('stock')
const wizardForm = reactive({
  room_id: '',
  rack_ids: [] as string[],
  per_rack_count: 1,
  start_u: 1,
  gap_u: 1,
})
const wizardNewRows = ref<BatchMountNewDevice[]>([])
const wizardPreview = ref<string[]>([])
const wizardSubmitting = ref(false)

const paramDialogVisible = ref(false)
const paramEditingId = ref<string | null>(null)
const bmcDialogVisible = ref(false)
const bmcEditingId = ref<string | null>(null)
const systemDialogVisible = ref(false)
const systemEditingId = ref<string | null>(null)
const osInput = ref('')
const paramForm = reactive({
  code: '',
  name: '',
  description: '',
  cpu_cores: null as number | null,
  cpu_architecture: null as 'c86' | 'arm' | null,
  cpu_model: '',
  memory_size_gb: null as number | null,
  memory_ddr_type: '' as string,
  memory_modules: null as number | null,
  disks: [] as ParamDiskSpec[],
  fan_count: null as number | null,
  fan_model: '',
  psu_power_w: null as number | null,
  raid_model: '',
  raid_params: '',
  supported_os: [] as string[],
  custom: [] as ParamCustomField[],
})

const DDR_OPTIONS = ['DDR3', 'DDR4', 'DDR5', 'LPDDR4', 'LPDDR5']
const DISK_INTERFACE_OPTIONS = ['SATA', 'SAS', 'NVMe', 'PCIe', 'M.2', 'U.2']
const DISK_MEDIA_OPTIONS = [
  { value: 'ssd', label: 'SSD' },
  { value: 'hdd', label: '机械盘' },
  { value: 'nvme', label: 'NVMe' },
]

const typeDialogVisible = ref(false)
const typeEditingId = ref<string | null>(null)
const typeSaving = ref(false)
const typeForm = reactive({
  code: '',
  name: '',
  description: '',
})

function resetTypeForm() {
  typeForm.code = ''
  typeForm.name = ''
  typeForm.description = ''
}

function openTypeCreate() {
  typeEditingId.value = null
  resetTypeForm()
  typeDialogVisible.value = true
}

function openTypeEdit(row: DeviceType) {
  typeEditingId.value = row.id
  typeForm.code = row.code
  typeForm.name = row.name
  typeForm.description = row.description || ''
  typeDialogVisible.value = true
}

function genTypeCode(name: string) {
  const ascii = name
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 40)
  if (ascii) return ascii
  return `TYPE_${Date.now().toString(36).toUpperCase()}`
}

async function ensureDeviceType(value: string | null): Promise<string | null> {
  if (!value) return null
  if (types.value.some((t) => t.id === value)) return value
  const name = value.trim()
  if (!name) return null
  const byName = types.value.find((t) => t.name === name || t.code === name)
  if (byName) return byName.id
  let code = genTypeCode(name)
  if (types.value.some((t) => t.code === code)) {
    code = `${code}_${Date.now().toString(36).toUpperCase()}`.slice(0, 50)
  }
  const created = await createDeviceType({ code, name, description: null })
  types.value = [...types.value, created].sort((a, b) => a.code.localeCompare(b.code))
  ElMessage.success(`已新建设备类型「${created.name}」`)
  return created.id
}

async function onDeviceTypeSelect(value: string | null) {
  try {
    form.device_type_id = await ensureDeviceType(value)
  } catch (error: unknown) {
    form.device_type_id = null
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '创建设备类型失败')
  }
}

async function saveTypeForm() {
  if (!typeForm.name.trim()) {
    ElMessage.warning('请填写类型名称')
    return
  }
  if (!typeEditingId.value && !typeForm.code.trim()) {
    typeForm.code = genTypeCode(typeForm.name)
  }
  if (!typeForm.code.trim()) {
    ElMessage.warning('请填写类型编码')
    return
  }
  typeSaving.value = true
  try {
    if (typeEditingId.value) {
      await updateDeviceType(typeEditingId.value, {
        code: typeForm.code.trim(),
        name: typeForm.name.trim(),
        description: typeForm.description.trim() || null,
      })
      ElMessage.success('设备类型已更新')
    } else {
      await createDeviceType({
        code: typeForm.code.trim(),
        name: typeForm.name.trim(),
        description: typeForm.description.trim() || null,
      })
      ElMessage.success('设备类型已创建')
    }
    typeDialogVisible.value = false
    await loadProfileRefs()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '保存失败')
  } finally {
    typeSaving.value = false
  }
}

async function removeType(row: DeviceType) {
  if (row.is_system) {
    ElMessage.warning('系统内置类型不可删除')
    return
  }
  await ElMessageBox.confirm(`确定删除设备类型「${row.name}」吗？`, '确认删除', { type: 'warning' })
  try {
    await deleteDeviceType(row.id)
    ElMessage.success('已删除')
    if (form.device_type_id === row.id) form.device_type_id = null
    await loadProfileRefs()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '删除失败')
  }
}

const modelDialogVisible = ref(false)
const modelEditingId = ref<string | null>(null)
const modelSaving = ref(false)
const modelForm = reactive({
  code: '',
  name: '',
  height_u: 1,
  power: null as number | null,
  description: '',
})

function genModelCode(name: string) {
  const ascii = name
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 40)
  if (ascii) return ascii
  return `MODEL_${Date.now().toString(36).toUpperCase()}`
}

function genMfgCode(name: string) {
  const ascii = name
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 40)
  if (ascii) return `MFG_${ascii}`
  return `MFG_${Date.now().toString(36).toUpperCase()}`
}

interface ContractModelEntry {
  modelName: string
  manufacturerName: string | null
}

function collectContractModelEntries(): ContractModelEntry[] {
  const map = new Map<string, ContractModelEntry>()
  for (const contract of contracts.value) {
    for (const item of normalizeContractItems(contract)) {
      const modelName = item.device_model_name?.trim()
      if (!modelName) continue
      const key = modelName.toLowerCase()
      const manufacturerName = item.manufacturer_name?.trim() || null
      const existing = map.get(key)
      if (!existing || (manufacturerName && !existing.manufacturerName)) {
        map.set(key, { modelName, manufacturerName })
      }
    }
  }
  return [...map.values()]
}

function findModelByName(modelName: string) {
  const key = modelName.trim().toLowerCase()
  return models.value.find(
    (m) => m.name.trim().toLowerCase() === key || m.code.trim().toLowerCase() === key,
  )
}

async function loadManufacturers() {
  manufacturers.value = await listManufacturers()
}

async function ensureManufacturer(name: string | null): Promise<string | undefined> {
  const trimmed = name?.trim()
  if (!trimmed) return undefined
  let mfg = manufacturers.value.find((m) => m.name === trimmed)
  if (mfg) return mfg.id
  let code = genMfgCode(trimmed)
  if (manufacturers.value.some((m) => m.code === code)) {
    code = `${code}_${Date.now().toString(36).toUpperCase()}`.slice(0, 50)
  }
  try {
    mfg = await createManufacturer({ code, name: trimmed })
    manufacturers.value = [...manufacturers.value, mfg].sort((a, b) =>
      a.name.localeCompare(b.name),
    )
    return mfg.id
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    const msg = err.response?.data?.message || err.message || ''
    if (msg.includes('already exists') || msg.includes('已存在')) {
      await loadManufacturers()
      mfg = manufacturers.value.find((m) => m.name === trimmed || m.code === code)
      return mfg?.id
    }
    throw error
  }
}

async function syncModelsFromContracts(options?: { quiet?: boolean }) {
  if (!auth.hasPermission('device:create')) return 0
  const entries = collectContractModelEntries()
  if (!entries.length) return 0
  let created = 0
  for (const entry of entries) {
    if (findModelByName(entry.modelName)) continue
    let code = genModelCode(entry.modelName)
    if (models.value.some((m) => m.code === code)) {
      code = `${code}_${Date.now().toString(36).toUpperCase()}`.slice(0, 50)
    }
    const manufacturerId = await ensureManufacturer(entry.manufacturerName)
    try {
      const createdModel = await createDeviceModel({
        code,
        name: entry.modelName,
        manufacturer_id: manufacturerId,
        height_u: 1,
        description: '来自合同信息同步',
      })
      models.value = [...models.value, createdModel].sort((a, b) => a.name.localeCompare(b.name))
      created += 1
    } catch (error: unknown) {
      const err = error as { response?: { data?: { message?: string } }; message?: string }
      const msg = err.response?.data?.message || err.message || ''
      if (msg.includes('已存在') || msg.includes('already exists')) {
        await loadProfileRefs()
        continue
      }
      if (!options?.quiet) throw error
    }
  }
  if (created > 0 && !options?.quiet) {
    ElMessage.success(`已从合同同步 ${created} 个设备型号`)
  }
  return created
}

async function handleSyncModelsFromContracts() {
  syncModelsLoading.value = true
  try {
    await loadLocationRefs()
    await loadManufacturers()
    const created = await syncModelsFromContracts()
    if (created === 0) ElMessage.info('合同中的设备型号均已存在，无需同步')
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '从合同同步型号失败')
  } finally {
    syncModelsLoading.value = false
  }
}

function resetModelForm() {
  modelForm.code = ''
  modelForm.name = ''
  modelForm.height_u = form.height_u || 1
  modelForm.power = form.power
  modelForm.description = ''
}

function openModelCreate() {
  modelEditingId.value = null
  resetModelForm()
  modelDialogVisible.value = true
}

function openModelEdit(row: DeviceModel) {
  modelEditingId.value = row.id
  modelForm.code = row.code
  modelForm.name = row.name
  modelForm.height_u = row.height_u
  modelForm.power = row.power
  modelForm.description = row.description || ''
  modelDialogVisible.value = true
}

async function removeModel(row: DeviceModel) {
  await ElMessageBox.confirm(`确定删除型号「${row.name}」吗？`, '确认删除', { type: 'warning' })
  try {
    await deleteDeviceModel(row.id)
    ElMessage.success('已删除')
    if (form.device_model_id === row.id) form.device_model_id = ''
    await loadProfileRefs()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '删除失败')
  }
}

async function ensureDeviceModel(
  value: string | null,
  opts?: { height_u?: number | null; power?: number | null },
): Promise<string | null> {
  if (!value) return null
  if (models.value.some((m) => m.id === value)) return value
  const name = value.trim()
  if (!name) return null
  const byName = models.value.find((m) => m.name === name || m.code === name)
  if (byName) return byName.id
  let code = genModelCode(name)
  if (models.value.some((m) => m.code === code)) {
    code = `${code}_${Date.now().toString(36).toUpperCase()}`.slice(0, 50)
  }
  const created = await createDeviceModel({
    code,
    name,
    height_u: opts?.height_u || form.height_u || 1,
    power: opts?.power ?? form.power ?? null,
    description: null,
  })
  models.value = [...models.value, created].sort((a, b) => a.name.localeCompare(b.name))
  ElMessage.success(`已新建型号「${created.name}」`)
  return created.id
}

async function onDeviceModelSelect(value: string | null) {
  try {
    const id = await ensureDeviceModel(value)
    form.device_model_id = id || ''
    const model = models.value.find((m) => m.id === id)
    if (model) {
      form.height_u = model.height_u
      form.power = model.power
    }
  } catch (error: unknown) {
    form.device_model_id = ''
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '创建型号失败')
  }
}

async function saveModelForm() {
  if (!modelForm.name.trim()) {
    ElMessage.warning('请填写型号名称')
    return
  }
  modelSaving.value = true
  try {
    const name = modelForm.name.trim()
    if (modelEditingId.value) {
      const updated = await updateDeviceModel(modelEditingId.value, {
        code: modelForm.code.trim() || undefined,
        name,
        height_u: modelForm.height_u,
        power: modelForm.power,
        description: modelForm.description.trim() || null,
      })
      const idx = models.value.findIndex((m) => m.id === updated.id)
      if (idx >= 0) models.value[idx] = updated
      else models.value = [...models.value, updated]
      models.value = [...models.value].sort((a, b) => a.name.localeCompare(b.name))
      if (form.device_model_id === updated.id) {
        form.height_u = updated.height_u
        form.power = updated.power
      }
      ElMessage.success('型号已更新')
    } else {
      let code = modelForm.code.trim() || genModelCode(name)
      if (models.value.some((m) => m.code === code)) {
        code = `${code}_${Date.now().toString(36).toUpperCase()}`.slice(0, 50)
      }
      const created = await createDeviceModel({
        code,
        name,
        height_u: modelForm.height_u,
        power: modelForm.power,
        description: modelForm.description.trim() || null,
      })
      models.value = [...models.value, created].sort((a, b) => a.name.localeCompare(b.name))
      form.device_model_id = created.id
      form.height_u = created.height_u
      form.power = created.power
      ElMessage.success(`已新建型号「${created.name}」`)
    }
    modelDialogVisible.value = false
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '保存型号失败')
  } finally {
    modelSaving.value = false
  }
}

async function onWizardModelChange(row: BatchMountNewDevice, value: string | null) {
  try {
    row.device_model_id = (await ensureDeviceModel(value, { height_u: row.height_u })) || ''
  } catch (error: unknown) {
    row.device_model_id = ''
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '创建型号失败')
  }
}

const ROLE_OPTIONS: { value: CredentialRole; label: string }[] = [
  { value: 'admin', label: '管理员' },
  { value: 'readonly', label: '只读用户' },
  { value: 'operator', label: '操作员' },
  { value: 'custom', label: '自定义' },
]

const OS_TYPE_OPTIONS: { value: OsType; label: string }[] = [
  { value: 'linux', label: 'Linux' },
  { value: 'windows', label: 'Windows' },
  { value: 'unix', label: 'Unix' },
  { value: 'esxi', label: 'ESXi' },
  { value: 'other', label: '其他' },
]

const bmcForm = reactive({
  code: '',
  name: '',
  description: '',
  users: [] as CredentialAccount[],
})

const systemForm = reactive({
  code: '',
  name: '',
  description: '',
  os_type: null as OsType | null,
  os_name: '',
  users: [] as CredentialAccount[],
  custom_users: [] as CredentialAccount[],
})

function emptyCredential(): CredentialAccount {
  return { username: '', password: '', role: 'admin', note: '' }
}

function mapCredentialForEdit(u: CredentialAccount): CredentialAccount {
  return {
    username: u.username || '',
    password: u.password_set ? MASKED_PASSWORD : u.password || '',
    role: u.role || 'admin',
    note: u.note || '',
  }
}

function mapCredentialsForSave(users: CredentialAccount[]): CredentialAccount[] {
  return users
    .filter((u) => u.username.trim())
    .map((u) => ({
      username: u.username.trim(),
      password: u.password || null,
      role: u.role || 'admin',
      note: u.note?.trim() || null,
    }))
}

function resetBmcForm() {
  bmcForm.code = ''
  bmcForm.name = ''
  bmcForm.description = ''
  bmcForm.users = [emptyCredential()]
}

function fillBmcForm(row: BmcProfile) {
  const p = row.payload || {}
  bmcForm.code = row.code
  bmcForm.name = row.name
  bmcForm.description = row.description || ''
  bmcForm.users = p.users?.length ? p.users.map(mapCredentialForEdit) : [emptyCredential()]
}

function buildBmcPayload(): BmcProfilePayload {
  return { users: mapCredentialsForSave(bmcForm.users) }
}

function addBmcUser() {
  bmcForm.users.push(emptyCredential())
}

function removeBmcUser(idx: number) {
  if (bmcForm.users.length <= 1) {
    bmcForm.users[0] = emptyCredential()
    return
  }
  bmcForm.users.splice(idx, 1)
}

function resetSystemForm() {
  systemForm.code = ''
  systemForm.name = ''
  systemForm.description = ''
  systemForm.os_type = null
  systemForm.os_name = ''
  systemForm.users = [emptyCredential()]
  systemForm.custom_users = []
}

function fillSystemForm(row: SystemProfile) {
  const p = row.payload || {}
  systemForm.code = row.code
  systemForm.name = row.name
  systemForm.description = row.description || ''
  systemForm.os_type = p.os_type ?? null
  systemForm.os_name = p.os_name || ''
  systemForm.users = p.users?.length ? p.users.map(mapCredentialForEdit) : [emptyCredential()]
  systemForm.custom_users = (p.custom_users || []).map(mapCredentialForEdit)
}

function buildSystemPayload(): SystemProfilePayload {
  return {
    os_type: systemForm.os_type,
    os_name: systemForm.os_name || null,
    users: mapCredentialsForSave(systemForm.users),
    custom_users: mapCredentialsForSave(systemForm.custom_users),
  }
}

function addSystemUser() {
  systemForm.users.push(emptyCredential())
}

function removeSystemUser(idx: number) {
  if (systemForm.users.length <= 1) {
    systemForm.users[0] = emptyCredential()
    return
  }
  systemForm.users.splice(idx, 1)
}

function addSystemCustomUser() {
  systemForm.custom_users.push(emptyCredential())
}

function removeSystemCustomUser(idx: number) {
  systemForm.custom_users.splice(idx, 1)
}

const DEFAULT_DISK_SPEC_COUNT = 3
const MAX_DISK_SPEC_COUNT = 20

function emptyDisk(): ParamDiskSpec {
  return { size_gb: null, count: null, interface: null, media_type: null }
}

function defaultDiskRows(count = DEFAULT_DISK_SPEC_COUNT): ParamDiskSpec[] {
  return Array.from({ length: count }, () => emptyDisk())
}

function isDiskRowFilled(d: ParamDiskSpec): boolean {
  return d.size_gb != null || d.count != null || !!d.interface || !!d.media_type
}

function resetParamForm() {
  paramForm.code = ''
  paramForm.name = ''
  paramForm.description = ''
  paramForm.cpu_cores = null
  paramForm.cpu_architecture = null
  paramForm.cpu_model = ''
  paramForm.memory_size_gb = null
  paramForm.memory_ddr_type = 'DDR5'
  paramForm.memory_modules = null
  paramForm.disks = defaultDiskRows()
  paramForm.fan_count = null
  paramForm.fan_model = ''
  paramForm.psu_power_w = null
  paramForm.raid_model = ''
  paramForm.raid_params = ''
  paramForm.supported_os = []
  paramForm.custom = []
  osInput.value = ''
}

function fillParamForm(row: ParamProfile) {
  const p = row.payload || {}
  paramForm.code = row.code
  paramForm.name = row.name
  paramForm.description = row.description || ''
  paramForm.cpu_cores = p.cpu?.cores ?? null
  paramForm.cpu_architecture = p.cpu?.architecture ?? null
  paramForm.cpu_model = p.cpu?.model || ''
  paramForm.memory_size_gb = p.memory?.size_gb ?? null
  paramForm.memory_ddr_type = p.memory?.ddr_type || 'DDR5'
  paramForm.memory_modules = p.memory?.modules ?? null
  paramForm.disks = p.disks?.length
    ? p.disks.map((d) => ({
        size_gb: d.size_gb ?? null,
        count: d.count ?? null,
        interface: d.interface ?? null,
        media_type: d.media_type ?? null,
      }))
    : defaultDiskRows()
  paramForm.fan_count = p.fan_count ?? null
  paramForm.fan_model = p.fan_model || ''
  paramForm.psu_power_w = p.psu_power_w ?? null
  paramForm.raid_model = p.raid?.model || ''
  paramForm.raid_params = p.raid?.params || ''
  paramForm.supported_os = [...(p.supported_os || [])]
  paramForm.custom = (p.custom || []).map((c) => ({ key: c.key, value: c.value }))
}

function buildParamPayload(): ParamProfilePayload {
  return {
    cpu: {
      cores: paramForm.cpu_cores,
      architecture: paramForm.cpu_architecture,
      model: paramForm.cpu_model || null,
    },
    memory: {
      size_gb: paramForm.memory_size_gb,
      ddr_type: paramForm.memory_ddr_type || null,
      modules: paramForm.memory_modules,
    },
    disks: paramForm.disks
      .filter(isDiskRowFilled)
      .map((d) => ({
        size_gb: d.size_gb ?? null,
        count: d.count ?? null,
        interface: d.interface || null,
        media_type: d.media_type || null,
      })),
    fan_count: paramForm.fan_count,
    fan_model: paramForm.fan_model || null,
    psu_power_w: paramForm.psu_power_w,
    raid: {
      model: paramForm.raid_model || null,
      params: paramForm.raid_params || null,
    },
    supported_os: [...paramForm.supported_os],
    custom: paramForm.custom.filter((c) => c.key.trim()),
  }
}

function addDiskRow() {
  if (paramForm.disks.length >= MAX_DISK_SPEC_COUNT) {
    ElMessage.warning(`最多添加 ${MAX_DISK_SPEC_COUNT} 种磁盘规格`)
    return
  }
  paramForm.disks.push(emptyDisk())
}

function removeDiskRow(idx: number) {
  if (paramForm.disks.length <= 1) {
    paramForm.disks[0] = emptyDisk()
    return
  }
  paramForm.disks.splice(idx, 1)
}

function addOsTag() {
  const v = osInput.value.trim()
  if (!v) return
  if (!paramForm.supported_os.includes(v)) paramForm.supported_os.push(v)
  osInput.value = ''
}

function removeOsTag(os: string) {
  paramForm.supported_os = paramForm.supported_os.filter((x) => x !== os)
}

function addCustomRow() {
  paramForm.custom.push({ key: '', value: '' })
}

function removeCustomRow(idx: number) {
  paramForm.custom.splice(idx, 1)
}

const canCreate = auth.hasPermission('device:create')
const canUpdate = auth.hasPermission('device:update')
const canDelete = auth.hasPermission('device:delete')
const canImport = auth.hasPermission('device:import')
const canExport = auth.hasPermission('device:export')
const canIoMenu = computed(() => canImport || canExport)
const importInput = ref<HTMLInputElement | null>(null)
const batchBusy = ref(false)

const BIND_TYPE_LABELS: Record<string, string> = {
  none: '未关联',
  device: '设备',
  rack: '机柜',
  rack_range: '机柜范围',
}

const BIND_TYPE_OPTIONS: { value: IpBindType; label: string }[] = [
  { value: 'none', label: '清除' },
  { value: 'device', label: '单设备' },
  { value: 'rack', label: '单机柜' },
  { value: 'rack_range', label: '机柜范围' },
]

const wizardRacks = computed(() =>
  racks.value.filter((r) => r.room_id === wizardForm.room_id),
)

/** 关联用机柜：可按机房筛选；有设备的机柜才列出 */
const ipBindRacks = computed(() =>
  racks.value.filter(
    (r) =>
      (!ipBindForm.room_id || r.room_id === ipBindForm.room_id) && (r.device_count ?? 0) > 0,
  ),
)

const filteredBindDevices = computed(() => {
  let list = bindDeviceOptions.value.filter((d) => !!d.rack_id)
  if (ipBindForm.room_id) {
    list = list.filter((d) => d.room_id === ipBindForm.room_id)
  }
  if (ipBindForm.rack_id) {
    list = list.filter((d) => d.rack_id === ipBindForm.rack_id)
  }
  if (ipBindForm.u_position != null) {
    list = list.filter((d) => {
      if (d.u_position == null) return false
      const end = d.u_position + (d.height_u || 1) - 1
      return ipBindForm.u_position! >= d.u_position && ipBindForm.u_position! <= end
    })
  }
  return list
})

/** 当前机柜内已占用的起始 U 选项（用于精确定位） */
const bindUOptions = computed(() => {
  const inRack = bindDeviceOptions.value
    .filter((d) => d.rack_id && (!ipBindForm.rack_id || d.rack_id === ipBindForm.rack_id))
    .filter((d) => !ipBindForm.room_id || d.room_id === ipBindForm.room_id)
    .filter((d) => d.u_position != null)
  const seen = new Set<number>()
  const opts: Array<{ u: number; device_id: string; label: string }> = []
  for (const d of [...inRack].sort((a, b) => (b.u_position || 0) - (a.u_position || 0))) {
    const u = d.u_position!
    if (seen.has(u)) continue
    seen.add(u)
    const name = d.name || d.hostname || d.serial_number
    const end = u + (d.height_u || 1) - 1
    opts.push({
      u,
      device_id: d.id,
      label: end > u ? `U${u}-U${end} · ${name}` : `U${u} · ${name}`,
    })
  }
  return opts
})

/** 机柜图：仅展示有设备的 U 格（起始位）便于点选，高 U 在上 */
const bindOccupiedSlots = computed(() =>
  ipBindLayoutSlots.value
    .filter((s) => s.occupied && s.is_span_start && s.device)
    .slice()
    .sort(
      (a, b) =>
        (b.device?.start_u || b.u_position) - (a.device?.start_u || a.u_position),
    ),
)

function bindDeviceLabel(d: Device) {
  const name = d.name || d.hostname || d.serial_number
  const loc = [d.room_name, d.rack_code, d.u_position != null ? `U${d.u_position}` : null]
    .filter(Boolean)
    .join(' / ')
  return loc ? `${name}（${loc}）` : name
}

async function loadBindRackLayout() {
  ipBindLayoutSlots.value = []
  ipBindLayoutCode.value = ''
  if (!ipBindForm.rack_id || ipBindForm.bind_type !== 'device') return
  ipBindLayoutLoading.value = true
  try {
    const data = await getRackLayout(ipBindForm.rack_id)
    ipBindLayoutSlots.value = data.slots || []
    ipBindLayoutCode.value = data.rack?.code || ''
  } catch {
    ipBindLayoutSlots.value = []
  } finally {
    ipBindLayoutLoading.value = false
  }
}

function onBindUSelect(u: number | null) {
  ipBindForm.u_position = u
  if (u == null) return
  const hit = bindUOptions.value.find((o) => o.u === u)
  if (hit) ipBindForm.device_id = hit.device_id
}

function selectBindSlot(slot: RackLayoutSlot) {
  if (!slot.device) return
  ipBindForm.device_id = slot.device.device_id
  ipBindForm.u_position = slot.device.start_u || slot.u_position
}

function onBindDeviceSelect(deviceId: string) {
  ipBindForm.device_id = deviceId
  const d = bindDeviceOptions.value.find((x) => x.id === deviceId)
  if (d?.u_position != null) ipBindForm.u_position = d.u_position
  if (d?.rack_id && d.rack_id !== ipBindForm.rack_id) {
    ipBindForm.rack_id = d.rack_id
    if (d.room_id) ipBindForm.room_id = d.room_id
  }
}

const ipAllocateRacks = computed(() =>
  racks.value.filter((r) => r.room_id === ipAllocateForm.room_id),
)

const statusLabel: Record<string, string> = {
  stock: '库存',
  mounted: '已上架',
  maintenance: '维护',
  retired: '退役',
}

async function loadProfileRefs() {
  const [modelList, typeList, params, bmcs, systems] = await Promise.all([
    listDeviceModels(),
    listDeviceTypes(),
    listParamProfiles(),
    listBmcProfiles(),
    listSystemProfiles(),
  ])
  models.value = modelList
  types.value = typeList
  paramProfiles.value = params
  bmcProfiles.value = bmcs
  systemProfiles.value = systems
}

async function loadLocationRefs() {
  const [roomData, rackData, contractData] = await Promise.all([
    listRooms({ page_size: 500 }),
    listRacks({ page_size: 500 }),
    listDeviceContracts({ page_size: 200 }),
  ])
  rooms.value = roomData?.items ?? []
  racks.value = rackData?.items ?? []
  contracts.value = contractData?.items ?? []
}

async function loadCatalog() {
  try {
    await Promise.all([loadProfileRefs(), loadLocationRefs(), loadManufacturers()])
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string; detail?: unknown } }; message?: string }
    const detail = err.response?.data?.message || err.message || ''
    ElMessage.error(detail ? `加载关联档案失败：${detail}` : '加载关联档案失败')
    return
  }
  try {
    await syncModelsFromContracts({ quiet: true })
  } catch {
    // 合同同步失败不阻断档案列表展示
  }
}

async function loadData() {
  loading.value = true
  try {
    const deviceData = await listDevices({
      page: pagination.page,
      page_size: pagination.page_size,
      keyword: keyword.value || undefined,
    })
    tableData.value = deviceData.items
    pagination.total = deviceData.pagination.total
  } catch {
    tableData.value = []
    ElMessage.error('加载设备列表失败')
  } finally {
    loading.value = false
  }
}

async function loadIpData() {
  ipLoading.value = true
  try {
    const data = await listIpAddresses({
      page: ipPagination.page,
      page_size: ipPagination.page_size,
      keyword: ipKeyword.value || undefined,
      status: ipStatusFilter.value || undefined,
    })
    ipTableData.value = data.items
    ipPagination.total = data.pagination.total
  } catch {
    ipTableData.value = []
    ElMessage.error('加载 IP 地址失败')
  } finally {
    ipLoading.value = false
  }
}

async function loadBindDevices() {
  if (!ipBindForm.room_id && !ipBindForm.rack_id) {
    bindDeviceOptions.value = []
    return
  }
  const pages: Device[] = []
  let page = 1
  let total = 0
  do {
    const data = await listDevices({
      page,
      page_size: 200,
      status: 'mounted',
      room_id: ipBindForm.room_id || undefined,
      rack_id: ipBindForm.rack_id || undefined,
    })
    pages.push(...(data.items || []))
    total = data.pagination?.total ?? pages.length
    page += 1
  } while (pages.length < total && page <= 10)
  bindDeviceOptions.value = pages.filter((d) => !!d.rack_id)
  // 当前所选设备若不在列表中则清空
  if (ipBindForm.device_id && !bindDeviceOptions.value.some((d) => d.id === ipBindForm.device_id)) {
    ipBindForm.device_id = ''
  }
}

function bindTypeLabel(bindType: string | null | undefined) {
  return BIND_TYPE_LABELS[bindType || 'none'] || bindType || '—'
}

function formatBindLocation(row: IpAddress) {
  if (row.bind_type === 'device') {
    const parts = [row.device_name]
    if (row.room_name && row.rack_code && row.u_position) {
      parts.push(`${row.room_name} / ${row.rack_code} / U${row.u_position}`)
    }
    return parts.filter(Boolean).join(' · ') || '—'
  }
  if (row.bind_type === 'rack') {
    return [row.room_name, row.rack_code].filter(Boolean).join(' / ') || '—'
  }
  if (row.bind_type === 'rack_range') {
    const room = row.room_name || '—'
    if (row.scope_rack_ids?.length) {
      const codes = row.scope_rack_ids
        .map((id) => racks.value.find((r) => r.id === id)?.code || id.slice(0, 8))
        .join(', ')
      return `${room} · ${codes}`
    }
    return room
  }
  return '—'
}

function onSelectionChange(rows: Device[]) {
  selectedDevices.value = rows
}

function onIpSelectionChange(rows: IpAddress[]) {
  selectedIps.value = rows
}

function resetForm() {
  form.name = ''
  form.hostname = ''
  form.serial_number = ''
  form.device_model_id = ''
  form.device_type_id = types.value[0]?.id || null
  form.param_profile_id = null
  form.bmc_profile_id = null
  form.system_profile_id = null
  form.contract_id = null
  form.height_u = 1
  form.power = null
  form.description = ''
  form.room_id = ''
  form.rack_id = ''
  form.u_position = 1
  originalMount.value = { rack_id: null, u_position: null }
  formLayoutSlots.value = []
  formLayoutTotalPower.value = 0
}

function openCreate() {
  editingId.value = null
  resetForm()
  editVisible.value = true
}

function openEdit(row: Device) {
  editingId.value = row.id
  form.name = row.name || row.hostname
  form.hostname = row.hostname
  form.serial_number = row.serial_number
  form.device_model_id = row.device_model_id
  form.device_type_id = row.device_type_id
  form.param_profile_id = row.param_profile_id
  form.bmc_profile_id = row.bmc_profile_id
  form.system_profile_id = row.system_profile_id
  form.contract_id = row.contract_id || null
  form.height_u = row.height_u
  form.power = row.power
  form.description = row.description || ''
  form.room_id = row.room_id || ''
  form.rack_id = row.rack_id || ''
  form.u_position = row.u_position || 1
  originalMount.value = {
    rack_id: row.rack_id || null,
    u_position: row.u_position || null,
  }
  editVisible.value = true
  if (form.rack_id) void loadFormRackLayout(form.rack_id)
}

async function openDeviceFromQuery() {
  const deviceId = route.query.device_id
  if (!deviceId || typeof deviceId !== 'string') return
  try {
    const device = await getDevice(deviceId)
    openEdit(device)
  } catch {
    ElMessage.warning('未找到指定设备')
  }
}

watch(
  () => form.device_model_id,
  (id) => {
    if (!editingId.value) {
      const model = models.value.find((m) => m.id === id)
      if (model) {
        form.height_u = model.height_u
        form.power = model.power
      }
    }
  },
)

async function loadFormRackLayout(rackId: string) {
  formLayoutSlots.value = []
  formLayoutTotalPower.value = 0
  if (!rackId) return
  formLayoutLoading.value = true
  try {
    const data = await getRackLayout(rackId)
    formLayoutSlots.value = data.slots || []
    formLayoutTotalPower.value = data.total_power || 0
  } catch {
    formLayoutSlots.value = []
  } finally {
    formLayoutLoading.value = false
  }
}

async function loadMountRackLayout(rackId: string) {
  mountLayoutSlots.value = []
  mountLayoutTotalPower.value = 0
  mountLayoutCode.value = ''
  if (!rackId) return
  mountLayoutLoading.value = true
  try {
    const data = await getRackLayout(rackId)
    mountLayoutSlots.value = data.slots || []
    mountLayoutTotalPower.value = data.total_power || 0
    mountLayoutCode.value = data.rack?.code || ''
  } catch {
    mountLayoutSlots.value = []
  } finally {
    mountLayoutLoading.value = false
  }
}

async function openRackDetail(row: Device) {
  if (!row.rack_id) return
  rackDetailDeviceId.value = row.id
  rackDetailVisible.value = true
  rackDetailLoading.value = true
  try {
    const data = await getRackLayout(row.rack_id)
    rackDetailRack.value = data.rack
    rackDetailSlots.value = data.slots || []
    rackDetailPower.value = data.total_power || 0
  } catch {
    rackDetailVisible.value = false
    ElMessage.error('加载机柜图失败')
  } finally {
    rackDetailLoading.value = false
  }
}

async function applyDeviceLocation(deviceId: string) {
  const hasLocation = !!form.rack_id && form.u_position != null && form.u_position > 0
  const prev = originalMount.value

  if (hasLocation) {
    const changed =
      !prev.rack_id || prev.rack_id !== form.rack_id || prev.u_position !== form.u_position
    if (changed) {
      await mountDevice(form.rack_id, deviceId, form.u_position!)
    }
  } else if (prev.rack_id) {
    await unmountDevice(deviceId)
  }
}

async function handleSubmit() {
  if (!form.serial_number || !form.device_model_id) {
    ElMessage.warning('请填写序列号与型号')
    return
  }
  const payload = {
    name: form.name || form.hostname || form.serial_number,
    hostname: form.hostname || form.name || form.serial_number,
    serial_number: form.serial_number,
    device_model_id: form.device_model_id,
    device_type_id: form.device_type_id || null,
    param_profile_id: form.param_profile_id || null,
    bmc_profile_id: form.bmc_profile_id || null,
    contract_id: form.contract_id || '',
    system_profile_id: form.system_profile_id || null,
    height_u: form.height_u,
    power: form.power,
    description: form.description || null,
  }
  try {
    let deviceId = editingId.value
    if (editingId.value) {
      await updateDevice(editingId.value, payload)
      deviceId = editingId.value
      ElMessage.success('已保存')
    } else {
      const created = await createDevice(payload)
      deviceId = created.id
      ElMessage.success('创建成功')
    }
    if (deviceId) {
      await applyDeviceLocation(deviceId)
    }
    editVisible.value = false
    await loadData()
  } catch {
    ElMessage.error('保存失败，请检查位置或参数是否正确')
  }
}

function isMessageBoxCancel(error: unknown): boolean {
  return error === 'cancel' || error === 'close'
}

async function handleDelete(row: Device) {
  if (row.rack_id) {
    ElMessage.warning('请先下架设备后再删除')
    return
  }
  try {
    await ElMessageBox.confirm(`确定删除设备「${row.name || row.hostname}」吗？`, '确认删除', {
      type: 'warning',
    })
    await deleteDevice(row.id)
    ElMessage.success('删除成功')
    await loadData()
  } catch (error: unknown) {
    if (isMessageBoxCancel(error)) return
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '删除失败')
  }
}

async function handleBatchDelete() {
  if (!selectedDevices.value.length) return
  const mounted = selectedDevices.value.filter((d) => d.rack_id)
  if (mounted.length === selectedDevices.value.length) {
    ElMessage.warning('选中的设备均已上架，请先下架后再删除')
    return
  }
  if (mounted.length) {
    ElMessage.warning(`已跳过 ${mounted.length} 台已上架设备，仅删除库存设备`)
  }
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${selectedDevices.value.length} 台设备吗？`, '批量删除', {
      type: 'warning',
    })
  } catch (error: unknown) {
    if (isMessageBoxCancel(error)) return
    throw error
  }
  batchBusy.value = true
  try {
    const result = await batchDeleteDevices(selectedDevices.value.map((d) => d.id))
    ElMessage.success(`删除 ${result.deleted} 台，跳过 ${result.skipped} 台`)
    if (result.errors.length) ElMessage.warning(result.errors.slice(0, 3).join('; '))
    await loadData()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '批量删除失败')
  } finally {
    batchBusy.value = false
  }
}

async function handleBatchUnmount() {
  const mounted = selectedDevices.value.filter((d) => d.rack_id)
  if (!mounted.length) {
    ElMessage.warning('请选择已上架设备')
    return
  }
  await ElMessageBox.confirm(`确定下架选中的 ${mounted.length} 台设备吗？`, '批量下架', {
    type: 'warning',
  })
  batchBusy.value = true
  try {
    const result = await batchUnmountDevices(mounted.map((d) => d.id))
    ElMessage.success(`下架 ${result.unmounted} 台，跳过 ${result.skipped} 台`)
    if (result.errors.length) ElMessage.warning(result.errors.slice(0, 3).join('; '))
    await loadData()
  } finally {
    batchBusy.value = false
  }
}

function openMount(row: Device) {
  mountForm.device_id = row.id
  mountForm.room_id = row.room_id || rooms.value[0]?.id || ''
  const roomRacks = racks.value.filter((r) => r.room_id === mountForm.room_id)
  mountForm.rack_id = row.rack_id || roomRacks[0]?.id || ''
  mountForm.u_position = row.u_position || 1
  mountVisible.value = true
  if (mountForm.rack_id) void loadMountRackLayout(mountForm.rack_id)
}

watch(
  () => mountForm.room_id,
  () => {
    const list = mountRacks.value
    if (!list.find((r) => r.id === mountForm.rack_id)) {
      mountForm.rack_id = list[0]?.id || ''
    }
  },
)

watch(
  () => mountForm.rack_id,
  (rackId) => {
    if (mountVisible.value && rackId) void loadMountRackLayout(rackId)
    else if (!rackId) {
      mountLayoutSlots.value = []
      mountLayoutTotalPower.value = 0
      mountLayoutCode.value = ''
    }
  },
)

watch(
  () => form.room_id,
  () => {
    const list = formRacks.value
    if (form.rack_id && !list.find((r) => r.id === form.rack_id)) {
      form.rack_id = ''
    }
  },
)

watch(
  () => form.rack_id,
  (rackId) => {
    if (editVisible.value && rackId) void loadFormRackLayout(rackId)
    else if (!rackId) {
      formLayoutSlots.value = []
      formLayoutTotalPower.value = 0
    }
  },
)

async function handleMount() {
  if (!mountForm.rack_id) {
    ElMessage.warning('请选择机柜')
    return
  }
  try {
    await mountDevice(mountForm.rack_id, mountForm.device_id, mountForm.u_position)
    ElMessage.success('上架成功')
    mountVisible.value = false
    await loadData()
  } catch {
    ElMessage.error('上架失败，U 位冲突或参数错误')
  }
}

async function handleUnmount(row: Device) {
  await unmountDevice(row.id)
  ElMessage.success('下架成功')
  await loadData()
}

function openBatchCreate() {
  batchCreateVisible.value = true
}

async function onBatchCreateSuccess() {
  // 批量新建不改变档案目录，仅刷新设备/IP，避免整页阻塞
  await loadData()
  if (activeTab.value === 'ips') {
    await loadIpData()
  }
}

function onTypeCreated(created: DeviceType) {
  if (types.value.some((t) => t.id === created.id)) return
  types.value = [...types.value, created].sort((a, b) => a.code.localeCompare(b.code))
}

function onModelCreated(created: DeviceModel) {
  if (models.value.some((m) => m.id === created.id)) return
  models.value = [...models.value, created].sort((a, b) => a.name.localeCompare(b.name))
}

async function onWizardTypeChange(row: BatchMountNewDevice, value: string | null) {
  try {
    row.device_type_id = await ensureDeviceType(value)
  } catch (error: unknown) {
    row.device_type_id = null
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '创建设备类型失败')
  }
}

function openWizard() {
  wizardStep.value = 0
  wizardSource.value = selectedDevices.value.some((d) => !d.rack_id) ? 'stock' : 'create'
  wizardForm.room_id = rooms.value[0]?.id || ''
  wizardForm.rack_ids = []
  wizardForm.per_rack_count = 1
  wizardForm.start_u = 1
  wizardForm.gap_u = 1
  wizardNewRows.value = [
    {
      name: '',
      hostname: '',
      serial_number: '',
      device_model_id: '',
      device_type_id: types.value[0]?.id || null,
      height_u: 1,
    },
  ]
  wizardPreview.value = []
  wizardVisible.value = true
}

function addWizardRow() {
  wizardNewRows.value.push({
    name: '',
    hostname: '',
    serial_number: '',
    device_model_id: '',
    device_type_id: types.value[0]?.id || null,
    height_u: models.value[0]?.height_u || 1,
  })
}

function buildWizardPreview() {
  const stockIds =
    wizardSource.value === 'stock'
      ? selectedDevices.value.filter((d) => !d.rack_id).map((d) => d.name || d.hostname)
      : []
  const created =
    wizardSource.value === 'create'
      ? wizardNewRows.value.filter((r) => r.serial_number).map((r) => r.name || r.serial_number)
      : []
  const targets = wizardForm.rack_ids.length
    ? wizardRacks.value.filter((r) => wizardForm.rack_ids.includes(r.id))
    : wizardRacks.value
  const roomName = rooms.value.find((r) => r.id === wizardForm.room_id)?.name || ''
  wizardPreview.value = [
    `机房：${roomName}`,
    `设备来源：${wizardSource.value === 'stock' ? `库存 ${stockIds.length} 台` : `新建 ${created.length} 台`}`,
    `目标机柜：${targets.length} 台（每柜最多 ${wizardForm.per_rack_count} 台）`,
    `起始 U：${wizardForm.start_u}，设备间隔：${wizardForm.gap_u}U`,
    `预计分配上限：${targets.length * wizardForm.per_rack_count} 台`,
  ]
}

async function nextWizardStep() {
  if (wizardStep.value === 0) {
    if (wizardSource.value === 'stock') {
      const stock = selectedDevices.value.filter((d) => !d.rack_id)
      if (!stock.length) {
        ElMessage.warning('请先勾选库存设备，或改用现场新建')
        return
      }
    } else if (!wizardNewRows.value.some((r) => r.serial_number && r.device_model_id)) {
      ElMessage.warning('请至少填写一台新建设备')
      return
    }
  }
  if (wizardStep.value === 1) {
    if (!wizardForm.room_id) {
      ElMessage.warning('请选择机房')
      return
    }
    if (!wizardRacks.value.length) {
      ElMessage.warning('该机房暂无机柜')
      return
    }
  }
  if (wizardStep.value === 2) {
    buildWizardPreview()
  }
  wizardStep.value += 1
}

async function submitWizard() {
  wizardSubmitting.value = true
  try {
    const payload = {
      room_id: wizardForm.room_id,
      device_ids:
        wizardSource.value === 'stock'
          ? selectedDevices.value.filter((d) => !d.rack_id).map((d) => d.id)
          : [],
      new_devices:
        wizardSource.value === 'create'
          ? wizardNewRows.value.filter((r) => r.serial_number && r.device_model_id)
          : [],
      rack_ids: wizardForm.rack_ids,
      per_rack_count: wizardForm.per_rack_count,
      start_u: wizardForm.start_u,
      gap_u: wizardForm.gap_u,
    }
    const result = await batchMountDevices(payload)
    ElMessage.success(
      `上架 ${result.mounted} 台，新建 ${result.created} 台，跳过 ${result.skipped} 台`,
    )
    if (result.errors.length) ElMessage.warning(result.errors.slice(0, 5).join('; '))
    wizardVisible.value = false
    await loadData()
  } catch {
    ElMessage.error('批量上架失败')
  } finally {
    wizardSubmitting.value = false
  }
}

function openProfileCreate() {
  if (profileSubTab.value === 'type') {
    openTypeCreate()
    return
  }
  if (profileSubTab.value === 'model') {
    openModelCreate()
    return
  }
  if (profileSubTab.value === 'param') {
    paramEditingId.value = null
    resetParamForm()
    paramDialogVisible.value = true
    return
  }
  if (profileSubTab.value === 'bmc') {
    bmcEditingId.value = null
    resetBmcForm()
    bmcDialogVisible.value = true
    return
  }
  systemEditingId.value = null
  resetSystemForm()
  systemDialogVisible.value = true
}

function openProfileEdit(row: ParamProfile | BmcProfile | SystemProfile | DeviceType | DeviceModel) {
  if (profileSubTab.value === 'type') {
    openTypeEdit(row as DeviceType)
    return
  }
  if (profileSubTab.value === 'model') {
    openModelEdit(row as DeviceModel)
    return
  }
  if (profileSubTab.value === 'param') {
    paramEditingId.value = row.id
    fillParamForm(row as ParamProfile)
    paramDialogVisible.value = true
    return
  }
  if (profileSubTab.value === 'bmc') {
    bmcEditingId.value = row.id
    fillBmcForm(row as BmcProfile)
    bmcDialogVisible.value = true
    return
  }
  systemEditingId.value = row.id
  fillSystemForm(row as SystemProfile)
  systemDialogVisible.value = true
}

async function saveParamProfile() {
  if (!paramForm.code || !paramForm.name) {
    ElMessage.warning('请填写编码与名称')
    return
  }
  const payload = buildParamPayload()
  if (paramEditingId.value) {
    await updateParamProfile(paramEditingId.value, {
      name: paramForm.name,
      payload,
      description: paramForm.description || null,
    })
  } else {
    await createParamProfile({
      code: paramForm.code,
      name: paramForm.name,
      payload,
      description: paramForm.description || null,
    })
  }
  ElMessage.success('参数档案已保存')
  paramDialogVisible.value = false
  await loadProfileRefs()
}

async function saveBmcProfile() {
  if (!bmcForm.code || !bmcForm.name) {
    ElMessage.warning('请填写编码与名称')
    return
  }
  const payload = buildBmcPayload()
  if (bmcEditingId.value) {
    await updateBmcProfile(bmcEditingId.value, {
      name: bmcForm.name,
      payload,
      description: bmcForm.description || null,
    })
  } else {
    await createBmcProfile({
      code: bmcForm.code,
      name: bmcForm.name,
      payload,
      description: bmcForm.description || null,
    })
  }
  ElMessage.success('BMC 档案已保存')
  bmcDialogVisible.value = false
  await loadProfileRefs()
}

async function saveSystemProfile() {
  if (!systemForm.code || !systemForm.name) {
    ElMessage.warning('请填写编码与名称')
    return
  }
  const payload = buildSystemPayload()
  if (systemEditingId.value) {
    await updateSystemProfile(systemEditingId.value, {
      name: systemForm.name,
      payload,
      description: systemForm.description || null,
    })
  } else {
    await createSystemProfile({
      code: systemForm.code,
      name: systemForm.name,
      payload,
      description: systemForm.description || null,
    })
  }
  ElMessage.success('系统用户档案已保存')
  systemDialogVisible.value = false
  await loadProfileRefs()
}

async function removeProfile(row: ParamProfile | BmcProfile | SystemProfile | DeviceType | DeviceModel) {
  if (profileSubTab.value === 'type') {
    await removeType(row as DeviceType)
    return
  }
  if (profileSubTab.value === 'model') {
    await removeModel(row as DeviceModel)
    return
  }
  await ElMessageBox.confirm(`确定删除档案「${row.name}」吗？`, '确认删除', { type: 'warning' })
  if (profileSubTab.value === 'param') await deleteParamProfile(row.id)
  else if (profileSubTab.value === 'bmc') await deleteBmcProfile(row.id)
  else await deleteSystemProfile(row.id)
  ElMessage.success('已删除')
  await loadProfileRefs()
}

function resetIpForm() {
  ipForm.system_ip = ''
  ipForm.bmc_ip = ''
  ipForm.vip = ''
  ipForm.netmask = '255.255.255.0'
  ipForm.gateway = ''
  ipForm.dns = ''
  ipForm.dns_secondary = ''
  ipForm.label = ''
  ipForm.description = ''
}

function openIpCreate() {
  ipEditingId.value = null
  resetIpForm()
  ipDialogVisible.value = true
}

function openIpEdit(row: IpAddress) {
  ipEditingId.value = row.id
  ipForm.system_ip = row.system_ip
  ipForm.bmc_ip = row.bmc_ip || ''
  ipForm.vip = row.vip || ''
  ipForm.netmask = row.netmask || ''
  ipForm.gateway = row.gateway || ''
  ipForm.dns = row.dns || ''
  ipForm.dns_secondary = row.dns_secondary || ''
  ipForm.label = row.label || ''
  ipForm.description = row.description || ''
  ipDialogVisible.value = true
}

async function saveIp() {
  if (!ipForm.system_ip.trim()) {
    ElMessage.warning('请填写系统 IP')
    return
  }
  const payload = {
    system_ip: ipForm.system_ip.trim(),
    bmc_ip: ipForm.bmc_ip.trim() || null,
    vip: ipForm.vip.trim() || null,
    netmask: ipForm.netmask.trim() || null,
    gateway: ipForm.gateway.trim() || null,
    dns: ipForm.dns.trim() || null,
    dns_secondary: ipForm.dns_secondary.trim() || null,
    label: ipForm.label.trim() || null,
    description: ipForm.description.trim() || null,
  }
  try {
    if (ipEditingId.value) {
      await updateIpAddress(ipEditingId.value, payload)
      ElMessage.success('已保存')
    } else {
      await createIpAddress(payload)
      ElMessage.success('创建成功')
    }
    ipDialogVisible.value = false
    await loadIpData()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string; detail?: string } }; message?: string }
    ElMessage.error(
      err.response?.data?.message || err.response?.data?.detail || err.message || '保存失败',
    )
  }
}

async function handleIpDelete(row: IpAddress) {
  await ElMessageBox.confirm(`确定删除 IP「${row.system_ip}」吗？`, '确认删除', { type: 'warning' })
  await deleteIpAddress(row.id)
  ElMessage.success('删除成功')
  await loadIpData()
}

function openIpBatchCreate() {
  ipBatchForm.start_system_ip = ''
  ipBatchForm.end_system_ip = ''
  ipBatchForm.start_bmc_ip = ''
  ipBatchForm.netmask = '255.255.255.0'
  ipBatchForm.gateway = ''
  ipBatchForm.dns = ''
  ipBatchForm.dns_secondary = ''
  ipBatchForm.label_prefix = ''
  ipBatchCreateVisible.value = true
}

async function submitIpBatchCreate(ev?: Event) {
  ev?.preventDefault?.()
  if (!ipBatchForm.start_system_ip.trim() || !ipBatchForm.end_system_ip.trim()) {
    ElMessage.warning('请填写系统 IP 起止地址')
    return
  }
  ipBatchBusy.value = true
  try {
    const result = await batchCreateIpAddresses({
      start_system_ip: ipBatchForm.start_system_ip.trim(),
      end_system_ip: ipBatchForm.end_system_ip.trim(),
      start_bmc_ip: ipBatchForm.start_bmc_ip.trim() || null,
      netmask: ipBatchForm.netmask.trim() || null,
      gateway: ipBatchForm.gateway.trim() || null,
      dns: ipBatchForm.dns.trim() || null,
      dns_secondary: ipBatchForm.dns_secondary.trim() || null,
      label_prefix: ipBatchForm.label_prefix.trim() || null,
    })
    if (!result) {
      ElMessage.error('生成失败：接口无返回数据')
      return
    }
    ElMessage.success(`生成 ${result.created} 条，跳过 ${result.skipped} 条`)
    if (result.errors?.length) ElMessage.warning(result.errors.slice(0, 5).join('; '))
    ipBatchCreateVisible.value = false
    await loadIpData()
  } catch (error: unknown) {
    const err = error as {
      response?: {
        data?: {
          message?: string
          detail?: string
          details?: { errors?: Array<{ msg?: string }> }
        }
      }
      message?: string
    }
    const validationMsgs = err.response?.data?.details?.errors
      ?.map((e) => e.msg)
      .filter(Boolean)
      .join('; ')
    ElMessage.error(
      validationMsgs
        || err.response?.data?.message
        || err.response?.data?.detail
        || err.message
        || '批量生成失败',
    )
  } finally {
    ipBatchBusy.value = false
  }
}

async function handleIpBatchDelete() {
  if (!selectedIps.value.length) return
  await ElMessageBox.confirm(`确定删除选中的 ${selectedIps.value.length} 条 IP 吗？`, '批量删除', {
    type: 'warning',
  })
  ipBatchBusy.value = true
  try {
    const result = await batchDeleteIpAddresses(selectedIps.value.map((ip) => ip.id))
    ElMessage.success(`删除 ${result.deleted} 条，跳过 ${result.skipped} 条`)
    if (result.errors.length) ElMessage.warning(result.errors.slice(0, 3).join('; '))
    await loadIpData()
  } finally {
    ipBatchBusy.value = false
  }
}

function resetIpBindForm() {
  ipBindForm.bind_type = 'device'
  ipBindForm.device_id = ''
  ipBindForm.room_id = ''
  ipBindForm.rack_id = ''
  ipBindForm.rack_ids = []
  ipBindForm.u_position = null
  ipBindLayoutSlots.value = []
  ipBindLayoutCode.value = ''
}

function buildBindPayload() {
  const bindType = ipBindForm.bind_type
  if (bindType === 'none') return { bind_type: 'none' as IpBindType }
  if (bindType === 'device') {
    return { bind_type: 'device' as IpBindType, device_id: ipBindForm.device_id || null }
  }
  if (bindType === 'rack') {
    return {
      bind_type: 'rack' as IpBindType,
      room_id: ipBindForm.room_id || null,
      rack_id: ipBindForm.rack_id || null,
    }
  }
  return {
    bind_type: 'rack_range' as IpBindType,
    room_id: ipBindForm.room_id || null,
    rack_ids: ipBindForm.rack_ids,
  }
}

async function openIpBindBatch() {
  if (!selectedIps.value.length) return
  ipBindMode.value = 'batch'
  ipBindTargetId.value = null
  resetIpBindForm()
  await loadBindDevices()
  ipBindVisible.value = true
}

async function handleIpBatchStatus(status: IpStatus) {
  if (!selectedIps.value.length) return
  const label = ipStatusLabel(status)
  await ElMessageBox.confirm(
    `将选中的 ${selectedIps.value.length} 条 IP 设为「${label}」？`,
    '确认',
    { type: 'warning' },
  )
  ipBatchBusy.value = true
  try {
    const result = await batchSetIpStatus(
      selectedIps.value.map((ip) => ip.id),
      status,
    )
    ElMessage.success(`已更新 ${result.updated} 条，跳过 ${result.skipped} 条`)
    if (result.errors?.length) ElMessage.warning(result.errors.slice(0, 5).join('; '))
    await loadIpData()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '状态更新失败')
  } finally {
    ipBatchBusy.value = false
  }
}

async function handleIpRelease(row: IpAddress) {
  await ElMessageBox.confirm(`释放 IP「${row.system_ip}」的关联？状态将恢复为空闲（禁用除外）。`, '确认释放', {
    type: 'warning',
  })
  try {
    await bindIpAddress(row.id, { bind_type: 'none' })
    ElMessage.success('已释放，状态已更新')
    await loadIpData()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '释放失败')
  }
}

async function handleIpToggleDisabled(row: IpAddress) {
  const next: IpStatus = row.status === 'disabled' ? 'free' : 'disabled'
  try {
    await batchSetIpStatus([row.id], next)
    ElMessage.success(next === 'disabled' ? '已禁用' : '已启用')
    await loadIpData()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '操作失败')
  }
}

async function openIpBindSingle(row: IpAddress) {
  ipBindMode.value = 'single'
  ipBindTargetId.value = row.id
  resetIpBindForm()
  if (row.bind_type && row.bind_type !== 'none') {
    ipBindForm.bind_type = row.bind_type as IpBindType
  }
  ipBindForm.device_id = row.device_id || ''
  ipBindForm.room_id = row.room_id || ''
  ipBindForm.rack_id = row.rack_id || ''
  ipBindForm.rack_ids = row.scope_rack_ids ? [...row.scope_rack_ids] : []
  ipBindForm.u_position = row.u_position ?? null
  await loadBindDevices()
  await loadBindRackLayout()
  ipBindVisible.value = true
}

watch(
  () => ipBindForm.room_id,
  async () => {
    const list = ipBindRacks.value
    if (ipBindForm.rack_id && !list.find((r) => r.id === ipBindForm.rack_id)) {
      ipBindForm.rack_id = ''
    }
    ipBindForm.rack_ids = ipBindForm.rack_ids.filter((id) => list.some((r) => r.id === id))
    if (ipBindForm.bind_type === 'device' && ipBindVisible.value) {
      await loadBindDevices()
    }
  },
)

watch(
  () => ipBindForm.rack_id,
  async () => {
    ipBindForm.u_position = null
    if (ipBindForm.bind_type === 'device' && ipBindVisible.value) {
      await loadBindDevices()
      await loadBindRackLayout()
    }
  },
)

watch(
  () => ipBindForm.bind_type,
  async (t) => {
    if (t === 'device' && ipBindVisible.value) {
      await loadBindDevices()
      await loadBindRackLayout()
    } else {
      ipBindLayoutSlots.value = []
      ipBindLayoutCode.value = ''
      ipBindForm.u_position = null
    }
  },
)

async function submitIpBind() {
  const bind = buildBindPayload()
  if (bind.bind_type === 'device') {
    if (!ipBindForm.rack_id) {
      ElMessage.warning('请选择机柜以便定位 U 位')
      return
    }
    if (!bind.device_id) {
      ElMessage.warning('请选择设备或点击机柜图中的 U 位')
      return
    }
  }
  if (bind.bind_type === 'rack' && !bind.rack_id) {
    ElMessage.warning('请选择机柜')
    return
  }
  if (bind.bind_type === 'rack_range' && !bind.room_id) {
    ElMessage.warning('请选择机房')
    return
  }
  if (bind.bind_type === 'rack_range' && !bind.rack_ids?.length) {
    ElMessage.warning('请选择机柜范围')
    return
  }

  ipBatchBusy.value = true
  try {
    if (ipBindMode.value === 'single' && ipBindTargetId.value) {
      await bindIpAddress(ipBindTargetId.value, bind)
      ElMessage.success('关联已更新')
    } else {
      const result = await batchBindIpAddresses(
        selectedIps.value.map((ip) => ip.id),
        bind,
      )
      ElMessage.success(`更新 ${result.updated} 条，跳过 ${result.skipped} 条`)
      if (result.errors.length) ElMessage.warning(result.errors.slice(0, 3).join('; '))
    }
    ipBindVisible.value = false
    await loadIpData()
  } finally {
    ipBatchBusy.value = false
  }
}

function openIpAllocate() {
  if (!selectedIps.value.length) return
  ipAllocateForm.room_id = rooms.value[0]?.id || ''
  ipAllocateForm.rack_ids = []
  ipAllocateVisible.value = true
}

watch(
  () => ipAllocateForm.room_id,
  () => {
    ipAllocateForm.rack_ids = ipAllocateForm.rack_ids.filter((id) =>
      ipAllocateRacks.value.some((r) => r.id === id),
    )
  },
)

async function submitIpAllocate() {
  if (!ipAllocateForm.room_id) {
    ElMessage.warning('请选择机房')
    return
  }
  ipBatchBusy.value = true
  try {
    const result = await allocateIpAddresses({
      ip_ids: selectedIps.value.map((ip) => ip.id),
      room_id: ipAllocateForm.room_id,
      rack_ids: ipAllocateForm.rack_ids,
    })
    ElMessage.success(`分配 ${result.allocated} 条，跳过 ${result.skipped} 条`)
    if (result.errors.length) ElMessage.warning(result.errors.slice(0, 5).join('; '))
    ipAllocateVisible.value = false
    await loadIpData()
    await loadData()
  } finally {
    ipBatchBusy.value = false
  }
}

async function handleExportExcel() {
  await exportDevicesExcel()
  ElMessage.success('Excel 导出成功')
}

async function handleExportPdf() {
  await exportDevicesPdf()
  ElMessage.success('PDF 导出成功')
}

function triggerImport() {
  importInput.value?.click()
}

async function handleIoCommand(command: string) {
  if (command === 'export-excel') {
    await handleExportExcel()
  } else if (command === 'export-pdf') {
    await handleExportPdf()
  } else if (command === 'import-excel') {
    triggerImport()
  }
}

async function handleImportFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    const result = await importDevices(file)
    ElMessage.success(`导入完成：成功 ${result.created} 条，失败 ${result.failed} 条`)
    if (result.errors.length) ElMessage.warning(result.errors.slice(0, 3).join('; '))
    await loadData()
  } catch {
    ElMessage.error('导入失败')
  } finally {
    input.value = ''
  }
}

const currentProfiles = computed(() => {
  if (profileSubTab.value === 'param') return paramProfiles.value
  if (profileSubTab.value === 'bmc') return bmcProfiles.value
  return systemProfiles.value
})

watch(activeTab, (tab) => {
  if (tab === 'ips') loadIpData()
  if (tab === 'profiles') void loadCatalog()
})

onMounted(() => {
  loading.value = true
  void Promise.all([loadCatalog(), loadData()]).finally(() => {
    loading.value = false
    void openDeviceFromQuery()
  })
})

watch(
  () => route.query.device_id,
  () => {
    void openDeviceFromQuery()
  },
)
</script>

<template>
  <div class="page">
    <el-card shadow="never">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="设备管理" name="devices">
          <div class="card-header">
            <div class="actions">
              <el-input
                v-model="keyword"
                placeholder="搜索名称/主机名/序列号"
                clearable
                style="width: 220px"
                @keyup.enter="loadData"
              />
              <el-button @click="loadData">搜索</el-button>
              <el-dropdown v-if="canIoMenu" trigger="click" @command="handleIoCommand">
                <el-button>
                  导入/导出
                  <span class="dropdown-caret">▾</span>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item v-if="canExport" command="export-excel">导出 Excel</el-dropdown-item>
                    <el-dropdown-item v-if="canExport" command="export-pdf">导出 PDF</el-dropdown-item>
                    <el-dropdown-item v-if="canImport" command="import-excel" :divided="canExport">
                      导入 Excel
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <input
                ref="importInput"
                type="file"
                accept=".xlsx,.xls"
                style="display: none"
                @change="handleImportFile"
              />
              <el-button v-if="canCreate" type="primary" @click="openCreate">新建</el-button>
              <el-button v-if="canCreate" type="primary" plain @click="openBatchCreate">
                批量新建
              </el-button>
              <el-button v-if="canUpdate" type="success" @click="openWizard">批量上架</el-button>
              <el-button
                v-if="canUpdate"
                :disabled="!selectedDevices.length"
                :loading="batchBusy"
                @click="handleBatchUnmount"
              >
                批量下架
              </el-button>
              <el-button
                v-if="canDelete"
                type="danger"
                :disabled="!selectedDevices.length"
                :loading="batchBusy"
                @click="handleBatchDelete"
              >
                批量删除
              </el-button>
              <span v-if="selectedDevices.length" class="batch-hint">已选 {{ selectedDevices.length }} 台</span>
            </div>
          </div>

          <el-table
            v-loading="loading"
            :data="tableData"
            stripe
            @selection-change="onSelectionChange"
          >
            <el-table-column type="selection" width="48" />
            <el-table-column prop="name" label="名称" min-width="120">
              <template #default="{ row }">{{ row.name || row.hostname }}</template>
            </el-table-column>
            <el-table-column prop="device_type_name" label="类型" width="90" />
            <el-table-column prop="device_model_name" label="型号" min-width="110" />
            <el-table-column prop="serial_number" label="序列号" min-width="120" />
            <el-table-column prop="height_u" label="高度" width="70" />
            <el-table-column prop="manufacturer_name" label="厂商" min-width="100" />
            <el-table-column label="合同" min-width="140">
              <template #default="{ row }">
                <div>{{ row.contract_no || '—' }}</div>
                <div v-if="row.project_no" class="ip-extra">项目: {{ row.project_no }}</div>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">{{ statusLabel[row.status] || row.status }}</template>
            </el-table-column>
            <el-table-column label="位置" min-width="160">
              <template #default="{ row }">
                <template v-if="row.rack_id">
                  {{ row.room_name || '—' }} / {{ row.rack_code || '—' }} / U{{ row.u_position }}
                </template>
                <template v-else>—</template>
              </template>
            </el-table-column>
            <el-table-column label="IP" min-width="150">
              <template #default="{ row }">
                <div>{{ row.ip_summary || '—' }}</div>
                <div v-if="row.bmc_ip || row.vip" class="ip-extra">
                  <span v-if="row.bmc_ip">BMC: {{ row.bmc_ip }}</span>
                  <span v-if="row.vip">VIP: {{ row.vip }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="280" fixed="right">
              <template #default="{ row }">
                <el-button v-if="canUpdate" type="primary" link @click="openEdit(row)">编辑</el-button>
                <el-button v-if="row.rack_id" type="primary" link @click="openRackDetail(row)">机柜图</el-button>
                <el-button v-if="canUpdate" type="primary" link @click="openMount(row)">
                  {{ row.rack_id ? '改位' : '上架' }}
                </el-button>
                <el-button v-if="canUpdate && row.rack_id" type="warning" link @click="handleUnmount(row)">
                  下架
                </el-button>
                <el-tooltip
                  v-if="canDelete"
                  :disabled="!row.rack_id"
                  content="请先下架设备后再删除"
                  placement="top"
                >
                  <el-button
                    type="danger"
                    link
                    :disabled="!!row.rack_id"
                    @click.stop="handleDelete(row)"
                  >
                    删除
                  </el-button>
                </el-tooltip>
              </template>
            </el-table-column>
          </el-table>

          <div class="pager">
            <el-pagination
              v-model:current-page="pagination.page"
              v-model:page-size="pagination.page_size"
              :total="pagination.total"
              layout="total, prev, pager, next"
              @current-change="loadData"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane label="关联档案" name="profiles">
          <el-tabs v-model="profileSubTab" type="card">
            <el-tab-pane label="参数档案" name="param" />
            <el-tab-pane label="BMC 档案" name="bmc" />
            <el-tab-pane label="系统用户档案" name="system" />
            <el-tab-pane label="设备类型" name="type" />
            <el-tab-pane label="设备型号" name="model" />
          </el-tabs>
          <div class="actions" style="margin-bottom: 12px">
            <el-button v-if="canUpdate" type="primary" @click="openProfileCreate">
              {{
                profileSubTab === 'type'
                  ? '新建类型'
                  : profileSubTab === 'model'
                    ? '新型号'
                    : '新建档案'
              }}
            </el-button>
            <el-button
              v-if="canCreate && profileSubTab === 'model'"
              :loading="syncModelsLoading"
              @click="handleSyncModelsFromContracts"
            >
              从合同同步型号
            </el-button>
          </div>
          <el-table v-if="profileSubTab === 'type'" :data="types" stripe>
            <el-table-column prop="code" label="编码" width="160" />
            <el-table-column prop="name" label="名称" min-width="140" />
            <el-table-column label="来源" width="100">
              <template #default="{ row }">
                <el-tag :type="row.is_system ? 'info' : 'success'" size="small">
                  {{ row.is_system ? '系统内置' : '自定义' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" min-width="200">
              <template #default="{ row }">{{ row.description || '—' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button v-if="canUpdate" type="primary" link @click="openTypeEdit(row)">编辑</el-button>
                <el-button
                  v-if="canUpdate && !row.is_system"
                  type="danger"
                  link
                  @click="removeType(row)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-table v-else-if="profileSubTab === 'model'" :data="models" stripe>
            <el-table-column prop="code" label="编码" width="160" />
            <el-table-column prop="name" label="型号名称" min-width="160" />
            <el-table-column prop="manufacturer_name" label="厂商" width="120">
              <template #default="{ row }">{{ row.manufacturer_name || '—' }}</template>
            </el-table-column>
            <el-table-column prop="description" label="描述" min-width="180">
              <template #default="{ row }">{{ row.description || '—' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button v-if="canUpdate" type="primary" link @click="openModelEdit(row)">
                  编辑
                </el-button>
                <el-button v-if="canUpdate" type="danger" link @click="removeModel(row)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-table v-else :data="currentProfiles" stripe>
            <el-table-column prop="code" label="编码" width="140" />
            <el-table-column prop="name" label="名称" min-width="120" />
            <el-table-column label="配置摘要" min-width="280">
              <template #default="{ row }">
                {{ row.summary || '—' }}
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" min-width="160" />
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button v-if="canUpdate" type="primary" link @click="openProfileEdit(row)">编辑</el-button>
                <el-button v-if="canUpdate" type="danger" link @click="removeProfile(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="IP 地址" name="ips">
          <div class="card-header">
            <div class="actions">
              <el-input
                v-model="ipKeyword"
                placeholder="搜索系统 IP / BMC / VIP / 标签"
                clearable
                style="width: 220px"
                @keyup.enter="loadIpData"
              />
              <el-select
                v-model="ipStatusFilter"
                clearable
                placeholder="地址状态"
                style="width: 120px"
                @change="loadIpData"
              >
                <el-option
                  v-for="o in IP_STATUS_OPTIONS"
                  :key="o.value"
                  :label="o.label"
                  :value="o.value"
                />
              </el-select>
              <el-button @click="loadIpData">搜索</el-button>
              <el-button v-if="canUpdate" type="primary" @click="openIpCreate">新建</el-button>
              <el-button v-if="canUpdate" @click="openIpBatchCreate">批量生成</el-button>
              <el-button
                v-if="canDelete"
                type="danger"
                :disabled="!selectedIps.length"
                :loading="ipBatchBusy"
                @click="handleIpBatchDelete"
              >
                批量删除
              </el-button>
              <el-button
                v-if="canUpdate"
                :disabled="!selectedIps.length"
                :loading="ipBatchBusy"
                @click="openIpBindBatch"
              >
                关联
              </el-button>
              <el-button
                v-if="canUpdate"
                type="success"
                :disabled="!selectedIps.length"
                :loading="ipBatchBusy"
                @click="openIpAllocate"
              >
                批量分配到机柜
              </el-button>
              <el-button
                v-if="canUpdate"
                :disabled="!selectedIps.length"
                :loading="ipBatchBusy"
                @click="handleIpBatchStatus('disabled')"
              >
                批量禁用
              </el-button>
              <el-button
                v-if="canUpdate"
                :disabled="!selectedIps.length"
                :loading="ipBatchBusy"
                @click="handleIpBatchStatus('free')"
              >
                批量启用
              </el-button>
              <span v-if="selectedIps.length" class="batch-hint">已选 {{ selectedIps.length }} 条</span>
            </div>
          </div>

          <el-table
            v-loading="ipLoading"
            :data="ipTableData"
            stripe
            @selection-change="onIpSelectionChange"
          >
            <el-table-column type="selection" width="48" />
            <el-table-column prop="system_ip" label="系统 IP" min-width="120" />
            <el-table-column prop="bmc_ip" label="BMC IP" min-width="120">
              <template #default="{ row }">
                <span :class="{ 'text-muted': !row.bmc_ip }">{{ row.bmc_ip || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="vip" label="VIP" min-width="120">
              <template #default="{ row }">
                <span :class="row.vip ? 'vip-highlight' : 'text-muted'">{{ row.vip || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="ipStatusMeta(row.status).type" size="small">
                  {{ ipStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="netmask" label="掩码" min-width="110">
              <template #default="{ row }">
                <span :class="{ 'text-muted': !row.netmask }">{{ row.netmask || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="gateway" label="网关" min-width="120">
              <template #default="{ row }">
                <span :class="{ 'text-muted': !row.gateway }">{{ row.gateway || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="DNS" min-width="140">
              <template #default="{ row }">
                <span :class="{ 'text-muted': !row.dns && !row.dns_secondary }">
                  {{
                    [row.dns, row.dns_secondary].filter(Boolean).join(' / ') || '—'
                  }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="label" label="标签" min-width="100">
              <template #default="{ row }">
                <span :class="{ 'text-muted': !row.label }">{{ row.label || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="关联类型" width="100">
              <template #default="{ row }">{{ bindTypeLabel(row.bind_type) }}</template>
            </el-table-column>
            <el-table-column label="关联位置" min-width="180">
              <template #default="{ row }">{{ formatBindLocation(row) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="260" fixed="right">
              <template #default="{ row }">
                <el-button v-if="canUpdate" type="primary" link @click="openIpEdit(row)">编辑</el-button>
                <el-button v-if="canUpdate" type="primary" link @click="openIpBindSingle(row)">关联</el-button>
                <el-button
                  v-if="canUpdate && row.bind_type !== 'none'"
                  type="warning"
                  link
                  @click="handleIpRelease(row)"
                >
                  释放
                </el-button>
                <el-button v-if="canUpdate" type="info" link @click="handleIpToggleDisabled(row)">
                  {{ row.status === 'disabled' ? '启用' : '禁用' }}
                </el-button>
                <el-button v-if="canDelete" type="danger" link @click="handleIpDelete(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="pager">
            <el-pagination
              v-model:current-page="ipPagination.page"
              v-model:page-size="ipPagination.page_size"
              :total="ipPagination.total"
              layout="total, prev, pager, next"
              @current-change="loadIpData"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-drawer
      v-model="editVisible"
      :title="editingId ? '编辑设备' : '新建设备'"
      size="720px"
    >
      <el-form label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="主机名">
          <el-input v-model="form.hostname" placeholder="默认与名称相同" />
        </el-form-item>
        <el-form-item label="序列号" required>
          <el-input v-model="form.serial_number" />
        </el-form-item>
        <el-form-item label="类型">
          <div class="type-select-row">
            <el-select
              v-model="form.device_type_id"
              clearable
              filterable
              allow-create
              default-first-option
              placeholder="选择或输入自定义类型"
              style="flex: 1"
              @change="onDeviceTypeSelect"
            >
              <el-option v-for="t in types" :key="t.id" :label="t.name" :value="t.id" />
            </el-select>
            <el-button v-if="canUpdate" @click="openTypeCreate">新建</el-button>
          </div>
        </el-form-item>
        <el-form-item label="型号" required>
          <div class="type-select-row">
            <el-select
              v-model="form.device_model_id"
              filterable
              allow-create
              default-first-option
              placeholder="输入自定义型号或选择已有"
              style="flex: 1"
              @change="onDeviceModelSelect"
            >
              <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.id" />
            </el-select>
            <el-button v-if="canCreate || canUpdate" @click="openModelCreate">新建</el-button>
          </div>
        </el-form-item>
        <el-form-item label="高度(U)">
          <el-input-number v-model="form.height_u" :min="1" :max="10" />
        </el-form-item>
        <el-form-item label="功率(W)">
          <el-input-number v-model="form.power" :min="0" :step="50" />
        </el-form-item>
        <el-divider content-position="left">上架位置</el-divider>
        <el-form-item label="机房">
          <el-select v-model="form.room_id" clearable filterable style="width: 100%" placeholder="选择机房">
            <el-option v-for="r in rooms" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="机柜">
          <el-select
            v-model="form.rack_id"
            clearable
            filterable
            style="width: 100%"
            placeholder="选择机柜"
            :disabled="!form.room_id"
          >
            <el-option
              v-for="r in formRacks"
              :key="r.id"
              :label="`${r.code} · 空闲 ${r.free_u}U`"
              :value="r.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="U 位">
          <el-input-number
            v-model="form.u_position"
            :min="1"
            :max="formRackMeta?.total_u || 60"
            :disabled="!form.rack_id"
          />
        </el-form-item>
        <el-form-item v-if="form.rack_id" label="机柜图">
          <div v-loading="formLayoutLoading" class="device-rack-preview">
            <RackCabinet
              selectable
              :code="formRackMeta?.code || '机柜'"
              :total-u="formRackMeta?.total_u || 42"
              :slots="formLayoutSlots"
              :total-power="formLayoutTotalPower"
              :selected-u="form.u_position"
              :highlight-device-id="editingId"
              compact
              @select-u="(u) => { form.u_position = u }"
            />
            <p class="bind-device-hint">点击空闲 U 位选择上架位置；已上架设备会高亮显示</p>
          </div>
        </el-form-item>
        <el-form-item label="参数档案">
          <el-select v-model="form.param_profile_id" clearable style="width: 100%" filterable>
            <el-option
              v-for="p in paramProfiles"
              :key="p.id"
              :label="p.summary ? `${p.name} · ${p.summary}` : p.name"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="BMC 档案">
          <el-select v-model="form.bmc_profile_id" clearable style="width: 100%" filterable>
            <el-option
              v-for="p in bmcProfiles"
              :key="p.id"
              :label="p.summary ? `${p.name} · ${p.summary}` : p.name"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="系统用户档案">
          <el-select v-model="form.system_profile_id" clearable style="width: 100%" filterable>
            <el-option
              v-for="p in systemProfiles"
              :key="p.id"
              :label="p.summary ? `${p.name} · ${p.summary}` : p.name"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="采购合同">
          <el-select
            v-model="form.contract_id"
            clearable
            filterable
            style="width: 100%"
            placeholder="选择采购合同"
          >
            <el-option
              v-for="c in formContracts"
              :key="c.id"
              :label="`${c.contract_no} · ${(c.device_items?.length ? c.device_items.map((i) => [i.device_name, i.device_model_name, i.manufacturer_name, i.quantity ? `×${i.quantity}` : null].filter(Boolean).join('/')).join('；') : [c.device_name, c.device_model_name, c.manufacturer_name].filter(Boolean).join(' / ')) || '—'}`"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存</el-button>
      </template>
    </el-drawer>

    <el-dialog v-model="mountVisible" title="手动上架 / 改位" width="880px" destroy-on-close>
      <div class="mount-layout">
        <el-form label-width="80px" class="mount-form">
          <el-form-item label="机房" required>
            <el-select v-model="mountForm.room_id" style="width: 100%" filterable>
              <el-option v-for="r in rooms" :key="r.id" :label="r.name" :value="r.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="机柜" required>
            <el-select v-model="mountForm.rack_id" style="width: 100%" filterable>
              <el-option
                v-for="r in mountRacks"
                :key="r.id"
                :label="`${r.code} · 空闲 ${r.free_u}U`"
                :value="r.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="U 位" required>
            <el-input-number
              v-model="mountForm.u_position"
              :min="1"
              :max="mountRackMeta?.total_u || 60"
            />
          </el-form-item>
          <p v-if="mountRackMeta" class="bind-device-hint">
            {{ mountRackMeta.code }} · {{ mountRackMeta.total_u }}U · 利用率 {{ mountRackMeta.utilization }}%
          </p>
        </el-form>
        <div v-loading="mountLayoutLoading" class="mount-preview">
          <RackCabinet
            v-if="mountForm.rack_id"
            selectable
            :code="mountRackMeta?.code || mountLayoutCode || '机柜'"
            :total-u="mountRackMeta?.total_u || 42"
            :slots="mountLayoutSlots"
            :total-power="mountLayoutTotalPower"
            :selected-u="mountForm.u_position"
            :highlight-device-id="mountForm.device_id"
            compact
            @select-u="(u) => { mountForm.u_position = u }"
          />
          <el-empty v-else description="请选择机柜" :image-size="64" />
          <p v-if="mountForm.rack_id" class="bind-device-hint">点击空闲 U 位快速选择上架位置</p>
        </div>
      </div>
      <template #footer>
        <el-button @click="mountVisible = false">取消</el-button>
        <el-button type="primary" @click="handleMount">确认</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="rackDetailVisible"
      :title="`机柜图 - ${rackDetailRack?.code || ''}`"
      size="480px"
    >
      <div v-loading="rackDetailLoading" class="layout-panel">
        <div v-if="rackDetailRack" class="layout-toolbar">
          <div class="layout-meta">
            <span>编号 {{ rackDetailRack.code }}</span>
            <span>已用 {{ rackDetailRack.occupied_u }}/{{ rackDetailRack.total_u }}U</span>
            <span>利用率 {{ rackDetailRack.utilization }}%</span>
          </div>
        </div>
        <RackCabinet
          v-if="rackDetailRack"
          :code="rackDetailRack.code"
          :total-u="rackDetailRack.total_u"
          :slots="rackDetailSlots"
          :total-power="rackDetailPower"
          :highlight-device-id="rackDetailDeviceId"
        />
      </div>
    </el-drawer>

    <BatchCreateDeviceDialog
      v-model="batchCreateVisible"
      :rooms="rooms"
      :racks="racks"
      :models="models"
      :types="types"
      @success="onBatchCreateSuccess"
      @type-created="onTypeCreated"
      @model-created="onModelCreated"
    />

    <el-dialog
      v-model="typeDialogVisible"
      :title="typeEditingId ? '编辑设备类型' : '新建设备类型'"
      width="480px"
      destroy-on-close
    >
      <el-form label-width="90px" @submit.prevent="saveTypeForm">
        <el-form-item label="编码" required>
          <el-input
            v-model="typeForm.code"
            :disabled="!!typeEditingId && types.find((t) => t.id === typeEditingId)?.is_system"
            placeholder="如 SERVER / SWITCH"
          />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="typeForm.name" placeholder="如 服务器、交换机" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="typeForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="typeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="typeSaving" @click="saveTypeForm">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="modelDialogVisible"
      :title="modelEditingId ? '编辑设备型号' : '新建自定义型号'"
      width="480px"
      destroy-on-close
    >
      <el-form label-width="90px" @submit.prevent="saveModelForm">
        <el-form-item label="编码">
          <el-input v-model="modelForm.code" placeholder="可选，默认按名称生成" />
        </el-form-item>
        <el-form-item label="型号名称" required>
          <el-input v-model="modelForm.name" placeholder="如 PowerEdge R740" />
        </el-form-item>
        <el-form-item label="默认高度">
          <el-input-number v-model="modelForm.height_u" :min="1" :max="10" />
          <span class="text-muted" style="margin-left: 8px">U（上架默认，不显示在型号名后）</span>
        </el-form-item>
        <el-form-item label="功率(W)">
          <el-input-number v-model="modelForm.power" :min="0" :step="50" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="modelForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="modelDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="modelSaving" @click="saveModelForm">
          {{ modelEditingId ? '保存' : '保存并选用' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="wizardVisible" title="批量上架向导" width="780px" destroy-on-close>
      <el-steps :active="wizardStep" finish-status="success" align-center style="margin-bottom: 20px">
        <el-step title="设备来源" />
        <el-step title="机房机柜" />
        <el-step title="分配策略" />
        <el-step title="确认提交" />
      </el-steps>

      <div v-if="wizardStep === 0">
        <el-radio-group v-model="wizardSource" style="margin-bottom: 16px">
          <el-radio-button value="stock">库存勾选</el-radio-button>
          <el-radio-button value="create">现场新建</el-radio-button>
        </el-radio-group>
        <div v-if="wizardSource === 'stock'">
          <el-alert
            type="info"
            :closable="false"
            :title="`将上架已勾选且未上架的设备：${selectedDevices.filter((d) => !d.rack_id).length} 台`"
          />
        </div>
        <div v-else>
          <div v-for="(row, idx) in wizardNewRows" :key="idx" class="wizard-row">
            <el-input v-model="row.name" placeholder="名称" style="width: 120px" />
            <el-input v-model="row.serial_number" placeholder="序列号*" style="width: 140px" />
            <el-select
              v-model="row.device_model_id"
              filterable
              allow-create
              default-first-option
              style="width: 180px"
              placeholder="自定义型号"
              @change="(v: string | null) => onWizardModelChange(row, v)"
            >
              <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.id" />
            </el-select>
            <el-select
              v-model="row.device_type_id"
              clearable
              filterable
              allow-create
              default-first-option
              style="width: 140px"
              placeholder="类型/自定义"
              @change="(v: string | null) => onWizardTypeChange(row, v)"
            >
              <el-option v-for="t in types" :key="t.id" :label="t.name" :value="t.id" />
            </el-select>
          </div>
          <el-button link type="primary" @click="addWizardRow">+ 添加一行</el-button>
        </div>
      </div>

      <div v-else-if="wizardStep === 1">
        <el-form label-width="90px">
          <el-form-item label="机房" required>
            <el-select v-model="wizardForm.room_id" style="width: 100%" filterable>
              <el-option v-for="r in rooms" :key="r.id" :label="r.name" :value="r.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="机柜范围">
            <RackRangePicker v-model="wizardForm.rack_ids" :racks="wizardRacks" empty-means-all />
          </el-form-item>
        </el-form>
      </div>

      <div v-else-if="wizardStep === 2">
        <el-form label-width="120px">
          <el-form-item label="起始 U 位">
            <el-input-number v-model="wizardForm.start_u" :min="1" :max="100" />
          </el-form-item>
          <el-form-item label="设备间隔">
            <el-input-number v-model="wizardForm.gap_u" :min="0" :max="10" />
            <span class="text-muted" style="margin-left: 8px">U（默认 1）</span>
          </el-form-item>
          <el-form-item label="每柜上架台数">
            <el-input-number v-model="wizardForm.per_rack_count" :min="1" :max="60" />
          </el-form-item>
          <el-alert
            type="info"
            :closable="false"
            title="从起始 U 起自动寻找空位，设备间保留间隔；上架后机柜位置图与设备数量同步更新"
          />
        </el-form>
      </div>

      <div v-else>
        <ul class="preview-list">
          <li v-for="(line, i) in wizardPreview" :key="i">{{ line }}</li>
        </ul>
      </div>

      <template #footer>
        <el-button v-if="wizardStep > 0" @click="wizardStep -= 1">上一步</el-button>
        <el-button v-if="wizardStep < 3" type="primary" @click="nextWizardStep">下一步</el-button>
        <el-button
          v-else
          type="primary"
          :loading="wizardSubmitting"
          @click="submitWizard"
        >
          确认上架
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="ipDialogVisible"
      :title="ipEditingId ? '编辑 IP 地址' : '新建 IP 地址'"
      width="560px"
    >
      <el-form label-width="100px" @submit.prevent>
        <el-form-item label="系统 IP" required>
          <el-input v-model="ipForm.system_ip" placeholder="必填" />
        </el-form-item>
        <el-form-item label="BMC IP">
          <el-input v-model="ipForm.bmc_ip" />
        </el-form-item>
        <el-form-item label="VIP">
          <el-input v-model="ipForm.vip" />
        </el-form-item>
        <el-form-item label="子网掩码">
          <el-input v-model="ipForm.netmask" placeholder="如 255.255.255.0 或 /24" />
        </el-form-item>
        <el-form-item label="网关">
          <el-input v-model="ipForm.gateway" placeholder="如 192.168.1.1" />
        </el-form-item>
        <el-form-item label="DNS">
          <el-input v-model="ipForm.dns" placeholder="可选" />
        </el-form-item>
        <el-form-item label="备用 DNS">
          <el-input v-model="ipForm.dns_secondary" placeholder="可选" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="ipForm.label" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="ipForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button native-type="button" @click="ipDialogVisible = false">取消</el-button>
        <el-button native-type="button" type="primary" @click="saveIp">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="ipBatchCreateVisible"
      title="批量生成 IP"
      width="560px"
      destroy-on-close
      @closed="ipBatchBusy = false"
    >
      <el-form label-width="110px" @submit.prevent="submitIpBatchCreate">
        <el-form-item label="起始系统 IP" required>
          <el-input v-model="ipBatchForm.start_system_ip" placeholder="如 192.168.1.10" />
        </el-form-item>
        <el-form-item label="结束系统 IP" required>
          <el-input v-model="ipBatchForm.end_system_ip" placeholder="如 192.168.1.20" />
        </el-form-item>
        <el-form-item label="起始 BMC IP">
          <el-input v-model="ipBatchForm.start_bmc_ip" placeholder="可选，与系统 IP 同步递增" />
        </el-form-item>
        <el-form-item label="子网掩码">
          <el-input v-model="ipBatchForm.netmask" placeholder="如 255.255.255.0 或 /24" />
        </el-form-item>
        <el-form-item label="网关">
          <el-input v-model="ipBatchForm.gateway" placeholder="如 192.168.1.1" />
        </el-form-item>
        <el-form-item label="DNS">
          <el-input v-model="ipBatchForm.dns" placeholder="可选" />
        </el-form-item>
        <el-form-item label="备用 DNS">
          <el-input v-model="ipBatchForm.dns_secondary" placeholder="可选" />
        </el-form-item>
        <el-form-item label="标签前缀">
          <el-input v-model="ipBatchForm.label_prefix" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button native-type="button" @click="ipBatchCreateVisible = false">取消</el-button>
        <el-button
          native-type="button"
          type="primary"
          :loading="ipBatchBusy"
          @click.prevent="submitIpBatchCreate"
        >
          生成
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="ipBindVisible"
      :title="ipBindMode === 'single' ? '关联 IP' : '批量关联 IP'"
      :width="
        ipBindForm.bind_type === 'rack_range'
          ? '720px'
          : ipBindForm.bind_type === 'device'
            ? '640px'
            : '560px'
      "
    >
      <el-form label-width="90px">
        <el-form-item label="关联方式" required>
          <el-select v-model="ipBindForm.bind_type" style="width: 100%">
            <el-option v-for="o in BIND_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <template v-if="ipBindForm.bind_type === 'device'">
          <el-form-item label="机房">
            <el-select
              v-model="ipBindForm.room_id"
              clearable
              filterable
              style="width: 100%"
              placeholder="先选机房便于定位"
            >
              <el-option v-for="r in rooms" :key="r.id" :label="r.name" :value="r.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="机柜" required>
            <el-select
              v-model="ipBindForm.rack_id"
              clearable
              filterable
              style="width: 100%"
              placeholder="选择机柜（仅显示有设备的机柜）"
            >
              <el-option
                v-for="r in ipBindRacks"
                :key="r.id"
                :label="`${r.code} · ${r.device_count} 台设备`"
                :value="r.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="U 位置">
            <el-select
              v-model="ipBindForm.u_position"
              clearable
              filterable
              style="width: 100%"
              placeholder="选择具体 U 位（自动选中该位设备）"
              :disabled="!ipBindForm.rack_id || !bindUOptions.length"
              @change="onBindUSelect"
            >
              <el-option
                v-for="o in bindUOptions"
                :key="o.u"
                :label="o.label"
                :value="o.u"
              />
            </el-select>
          </el-form-item>
          <el-form-item v-if="ipBindForm.rack_id" label="机柜图">
            <div v-loading="ipBindLayoutLoading" class="bind-u-map">
              <div class="bind-u-map-title">
                {{ ipBindLayoutCode || '机柜' }} · 点击设备所在 U 位定位
              </div>
              <div v-if="bindOccupiedSlots.length" class="bind-u-map-list">
                <button
                  v-for="slot in bindOccupiedSlots"
                  :key="slot.u_position"
                  type="button"
                  class="bind-u-slot"
                  :class="{
                    selected:
                      ipBindForm.device_id === slot.device?.device_id
                      || ipBindForm.u_position === slot.device?.start_u,
                  }"
                  @click="selectBindSlot(slot)"
                >
                  <span class="u-tag">
                    U{{ slot.device?.start_u || slot.u_position
                    }}{{
                      slot.span_height > 1
                        ? `-U${(slot.device?.start_u || slot.u_position) + slot.span_height - 1}`
                        : ''
                    }}
                  </span>
                  <span class="u-name">
                    {{ slot.device?.hostname || slot.device?.model_name || '设备' }}
                  </span>
                </button>
              </div>
              <p v-else-if="!ipBindLayoutLoading" class="bind-device-hint">该机柜暂无可选设备位</p>
            </div>
          </el-form-item>
          <el-form-item label="设备" required>
            <el-select
              v-model="ipBindForm.device_id"
              filterable
              style="width: 100%"
              placeholder="选择已上架设备"
              :disabled="!filteredBindDevices.length"
              @change="onBindDeviceSelect"
            >
              <el-option
                v-for="d in filteredBindDevices"
                :key="d.id"
                :label="bindDeviceLabel(d)"
                :value="d.id"
              />
            </el-select>
            <p v-if="ipBindForm.device_id && ipBindForm.u_position != null" class="bind-loc-summary">
              已定位：{{
                rooms.find((r) => r.id === ipBindForm.room_id)?.name || '—'
              }}
              /
              {{ ipBindRacks.find((r) => r.id === ipBindForm.rack_id)?.code || ipBindLayoutCode || '—' }}
              / U{{ ipBindForm.u_position }}
            </p>
            <p v-else-if="!filteredBindDevices.length" class="bind-device-hint">
              请先选择机柜与 U 位，或确认该位置有已上架设备
            </p>
          </el-form-item>
        </template>
        <template v-if="ipBindForm.bind_type === 'rack'">
          <el-form-item label="机房" required>
            <el-select v-model="ipBindForm.room_id" filterable style="width: 100%">
              <el-option v-for="r in rooms" :key="r.id" :label="r.name" :value="r.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="机柜" required>
            <el-select v-model="ipBindForm.rack_id" filterable style="width: 100%" placeholder="仅显示有设备的机柜">
              <el-option
                v-for="r in ipBindRacks"
                :key="r.id"
                :label="`${r.code} · ${r.device_count} 台设备`"
                :value="r.id"
              />
            </el-select>
          </el-form-item>
        </template>
        <template v-if="ipBindForm.bind_type === 'rack_range'">
          <el-form-item label="机房" required>
            <el-select v-model="ipBindForm.room_id" filterable style="width: 100%">
              <el-option v-for="r in rooms" :key="r.id" :label="r.name" :value="r.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="机柜范围" required>
            <RackRangePicker
              v-model="ipBindForm.rack_ids"
              :racks="ipBindRacks"
              :empty-means-all="false"
            />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="ipBindVisible = false">取消</el-button>
        <el-button type="primary" :loading="ipBatchBusy" @click="submitIpBind">确认</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="ipAllocateVisible" title="批量分配到机柜" width="720px" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="机房" required>
          <el-select v-model="ipAllocateForm.room_id" filterable style="width: 100%">
            <el-option v-for="r in rooms" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="机柜范围">
          <RackRangePicker v-model="ipAllocateForm.rack_ids" :racks="ipAllocateRacks" empty-means-all />
        </el-form-item>
        <el-alert
          type="info"
          :closable="false"
          title="按系统 IP 升序、机柜编号升序、低 U 位设备分配，设备间隔 1U"
        />
      </el-form>
      <template #footer>
        <el-button @click="ipAllocateVisible = false">取消</el-button>
        <el-button type="primary" :loading="ipBatchBusy" @click="submitIpAllocate">确认分配</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="paramDialogVisible"
      :title="paramEditingId ? '编辑参数档案' : '新建参数档案'"
      width="760px"
      destroy-on-close
      top="4vh"
    >
      <el-form label-width="100px" class="param-form">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="编码" required>
              <el-input v-model="paramForm.code" :disabled="!!paramEditingId" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名称" required>
              <el-input v-model="paramForm.name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述">
          <el-input v-model="paramForm.description" type="textarea" :rows="2" />
        </el-form-item>

        <div class="param-section-title">CPU</div>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="核心数">
              <el-input-number v-model="paramForm.cpu_cores" :min="1" :max="1024" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="架构">
              <el-select v-model="paramForm.cpu_architecture" clearable style="width: 100%" placeholder="选择架构">
                <el-option label="C86" value="c86" />
                <el-option label="ARM" value="arm" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="型号">
              <el-input v-model="paramForm.cpu_model" placeholder="可选" />
            </el-form-item>
          </el-col>
        </el-row>

        <div class="param-section-title">内存</div>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="大小(GB)">
              <el-input-number v-model="paramForm.memory_size_gb" :min="0" :step="8" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="DDR 类型">
              <el-select v-model="paramForm.memory_ddr_type" allow-create filterable style="width: 100%">
                <el-option v-for="d in DDR_OPTIONS" :key="d" :label="d" :value="d" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="条数">
              <el-input-number v-model="paramForm.memory_modules" :min="0" :max="128" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <div class="param-section-title">
          <span>磁盘规格（默认 {{ DEFAULT_DISK_SPEC_COUNT }} 种，可继续添加）</span>
          <el-button
            type="primary"
            link
            :disabled="paramForm.disks.length >= MAX_DISK_SPEC_COUNT"
            @click="addDiskRow"
          >
            + 添加磁盘规格
          </el-button>
        </div>
        <p class="disk-hint">
          每种规格填写：单盘容量、块数、接口与盘类型。未填写的规格不会保存。当前
          {{ paramForm.disks.length }} / {{ MAX_DISK_SPEC_COUNT }}
        </p>
        <div v-for="(disk, idx) in paramForm.disks" :key="idx" class="disk-row">
          <el-form-item :label="`规格 ${idx + 1}`" label-width="70px">
            <div class="disk-fields">
              <el-input-number
                v-model="disk.size_gb"
                :min="0"
                :step="100"
                placeholder="单盘GB"
                controls-position="right"
              />
              <span class="disk-field-label">GB ×</span>
              <el-input-number
                v-model="disk.count"
                :min="0"
                :max="100"
                placeholder="块数"
                controls-position="right"
              />
              <span class="disk-field-label">块</span>
              <el-select
                v-model="disk.interface"
                clearable
                allow-create
                filterable
                placeholder="接口"
                style="width: 110px"
              >
                <el-option v-for="i in DISK_INTERFACE_OPTIONS" :key="i" :label="i" :value="i" />
              </el-select>
              <el-select
                v-model="disk.media_type"
                clearable
                placeholder="盘类型"
                style="width: 110px"
              >
                <el-option
                  v-for="m in DISK_MEDIA_OPTIONS"
                  :key="m.value"
                  :label="m.label"
                  :value="m.value"
                />
              </el-select>
              <el-button type="danger" link @click="removeDiskRow(idx)">删除</el-button>
            </div>
          </el-form-item>
        </div>

        <div class="param-section-title">风扇 / 电源 / RAID</div>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="风扇数量">
              <el-input-number v-model="paramForm.fan_count" :min="0" :max="64" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="风扇型号">
              <el-input v-model="paramForm.fan_model" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="电源(W)">
              <el-input-number v-model="paramForm.psu_power_w" :min="0" :step="100" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="10">
            <el-form-item label="RAID 型号">
              <el-input v-model="paramForm.raid_model" placeholder="如 PERC H755" />
            </el-form-item>
          </el-col>
          <el-col :span="14">
            <el-form-item label="RAID 参数">
              <el-input v-model="paramForm.raid_params" placeholder="如 RAID10 / 缓存 8GB" />
            </el-form-item>
          </el-col>
        </el-row>

        <div class="param-section-title">支持的操作系统</div>
        <el-form-item label="操作系统">
          <div class="os-editor">
            <el-tag
              v-for="os in paramForm.supported_os"
              :key="os"
              closable
              style="margin-right: 6px; margin-bottom: 6px"
              @close="removeOsTag(os)"
            >
              {{ os }}
            </el-tag>
            <div class="os-add">
              <el-input
                v-model="osInput"
                placeholder="输入系统名后添加，如 Ubuntu 22.04"
                style="width: 260px"
                @keyup.enter="addOsTag"
              />
              <el-button @click="addOsTag">添加</el-button>
            </div>
          </div>
        </el-form-item>

        <div class="param-section-title">
          <span>自定义参数</span>
          <el-button type="primary" link @click="addCustomRow">+ 手动添加</el-button>
        </div>
        <div v-if="!paramForm.custom.length" class="custom-empty">暂无自定义参数，可点击「手动添加」</div>
        <div v-for="(item, idx) in paramForm.custom" :key="idx" class="custom-row">
          <el-input v-model="item.key" placeholder="参数名" style="width: 200px" />
          <el-input v-model="item.value" placeholder="参数值" style="flex: 1" />
          <el-button type="danger" link @click="removeCustomRow(idx)">删除</el-button>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="paramDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveParamProfile">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="bmcDialogVisible"
      :title="bmcEditingId ? '编辑 BMC 档案' : '新建 BMC 档案'"
      width="720px"
      destroy-on-close
      top="4vh"
    >
      <el-form label-width="100px" class="param-form">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="编码" required>
              <el-input v-model="bmcForm.code" :disabled="!!bmcEditingId" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名称" required>
              <el-input v-model="bmcForm.name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述">
          <el-input v-model="bmcForm.description" type="textarea" :rows="2" />
        </el-form-item>

        <div class="param-section-title">
          <span>BMC 用户</span>
          <el-button type="primary" link @click="addBmcUser">+ 添加 BMC 用户</el-button>
        </div>
        <div v-for="(user, idx) in bmcForm.users" :key="idx" class="credential-row">
          <el-input v-model="user.username" placeholder="用户名" style="width: 120px" />
          <el-input
            v-model="user.password"
            type="password"
            show-password
            placeholder="********"
            style="width: 140px"
          />
          <el-select v-model="user.role" placeholder="角色" style="width: 120px">
            <el-option v-for="r in ROLE_OPTIONS" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
          <el-input v-model="user.note" placeholder="备注" style="flex: 1" />
          <el-button type="danger" link @click="removeBmcUser(idx)">删除</el-button>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="bmcDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveBmcProfile">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="systemDialogVisible"
      :title="systemEditingId ? '编辑系统用户档案' : '新建系统用户档案'"
      width="760px"
      destroy-on-close
      top="4vh"
    >
      <el-form label-width="100px" class="param-form">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="编码" required>
              <el-input v-model="systemForm.code" :disabled="!!systemEditingId" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名称" required>
              <el-input v-model="systemForm.name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述">
          <el-input v-model="systemForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="操作系统">
              <el-select v-model="systemForm.os_type" clearable style="width: 100%" placeholder="选择类型">
                <el-option v-for="o in OS_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="系统名称">
              <el-input v-model="systemForm.os_name" placeholder="如 Ubuntu 22.04 / Windows Server 2022" />
            </el-form-item>
          </el-col>
        </el-row>

        <div class="param-section-title">
          <span>系统用户</span>
          <el-button type="primary" link @click="addSystemUser">+ 添加</el-button>
        </div>
        <div v-for="(user, idx) in systemForm.users" :key="`u-${idx}`" class="credential-row">
          <el-input v-model="user.username" placeholder="用户名" style="width: 120px" />
          <el-input
            v-model="user.password"
            type="password"
            show-password
            placeholder="********"
            style="width: 140px"
          />
          <el-select v-model="user.role" placeholder="角色" style="width: 120px">
            <el-option v-for="r in ROLE_OPTIONS" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
          <el-input v-model="user.note" placeholder="备注" style="flex: 1" />
          <el-button type="danger" link @click="removeSystemUser(idx)">删除</el-button>
        </div>

        <div class="param-section-title">
          <span>自定义系统用户</span>
          <el-button type="primary" link @click="addSystemCustomUser">+ 手动添加</el-button>
        </div>
        <div v-if="!systemForm.custom_users.length" class="custom-empty">暂无自定义用户，可点击「手动添加」</div>
        <div v-for="(user, idx) in systemForm.custom_users" :key="`c-${idx}`" class="credential-row">
          <el-input v-model="user.username" placeholder="用户名" style="width: 120px" />
          <el-input
            v-model="user.password"
            type="password"
            show-password
            placeholder="********"
            style="width: 140px"
          />
          <el-select v-model="user.role" placeholder="角色" style="width: 120px">
            <el-option v-for="r in ROLE_OPTIONS" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
          <el-input v-model="user.note" placeholder="备注" style="flex: 1" />
          <el-button type="danger" link @click="removeSystemCustomUser(idx)">删除</el-button>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="systemDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveSystemProfile">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.type-select-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.batch-hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.bind-device-hint {
  margin: 6px 0 0;
  color: var(--el-color-warning);
  font-size: 12px;
  line-height: 1.4;
}

.mount-layout {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(320px, 1fr);
  gap: 20px;
  align-items: start;
}

.mount-form {
  padding-top: 4px;
}

.mount-preview,
.device-rack-preview {
  min-width: 0;
}

.layout-panel {
  min-height: 200px;
}

.layout-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.layout-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: #606266;
  font-size: 13px;
}

@media (max-width: 860px) {
  .mount-layout {
    grid-template-columns: 1fr;
  }
}
.bind-loc-summary {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--el-color-primary);
}
.bind-u-map {
  width: 100%;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
  padding: 10px;
  min-height: 80px;
}
.bind-u-map-title {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}
.bind-u-map-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 280px;
  overflow-y: auto;
}
.bind-u-slot {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  background: var(--el-bg-color);
  cursor: pointer;
  font: inherit;
  color: var(--el-text-color-primary);
  transition: border-color 0.12s, background 0.12s;
}
.bind-u-slot:hover {
  border-color: var(--el-color-primary-light-3);
}
.bind-u-slot.selected {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}
.bind-u-slot .u-tag {
  flex-shrink: 0;
  min-width: 72px;
  font-weight: 600;
  font-size: 12px;
}
.bind-u-slot .u-name {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.wizard-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}
.preview-list {
  margin: 0;
  padding-left: 18px;
  line-height: 1.8;
}
.param-form {
  max-height: 70vh;
  overflow-y: auto;
  padding-right: 8px;
}
.param-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 12px 0 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.disk-row {
  margin-bottom: 4px;
}
.disk-hint {
  margin: -4px 0 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.disk-fields {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.disk-field-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}
.os-editor {
  width: 100%;
}
.os-add {
  display: flex;
  gap: 8px;
  margin-top: 6px;
}
.custom-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.custom-empty {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  margin: 0 0 8px 100px;
}
.credential-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
  padding-left: 100px;
}
.text-muted {
  color: var(--el-text-color-secondary);
}
.vip-highlight {
  color: var(--el-color-primary);
  font-weight: 500;
}
.ip-extra {
  margin-top: 2px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
