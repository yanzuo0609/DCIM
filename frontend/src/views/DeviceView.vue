<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  batchDeleteDevices,
  createBmcProfile,
  createDevice,
  createDeviceModel,
  createDeviceType,
  createManufacturer,
  createSystemProfile,
  deleteBmcProfile,
  deleteDevice,
  deleteDeviceModel,
  deleteDeviceType,
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
  updateSystemProfile,
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
  type DiskRole,
  type ParamProfile,
  type ParamProfilePayload,
  type SystemProfile,
  type SystemProfilePayload,
} from '@/api/device'
import {
  allocateIpAddresses,
  batchBindIpAddresses,
  batchDeleteIpAddresses,
  batchSetIpStatus,
  bindIpAddress,
  createIpSegment,
  deleteIpSegment,
  getIpSegment,
  listIpAddresses,
  listIpSegments,
  updateIpAddress,
  updateIpSegment,
  deleteIpAddress,
  type IpAddress,
  type IpBindType,
  type IpSegment,
  type IpSegmentDetail,
  type IpStatus,
} from '@/api/ip'
import {
  contractItemKey,
  findContractItem,
  listDeviceContracts,
  matchContractItemKey,
  syncContractModels,
  syncContractModelsById,
  type DeviceContract,
  type DeviceContractItem,
} from '@/api/contract'
import { getRackLayout, listRacks, type Rack, type RackLayoutSlot } from '@/api/rack'
import { listRooms, type Room } from '@/api/room'
import BatchCreateDeviceDialog from '@/components/BatchCreateDeviceDialog.vue'
import BatchEditDeviceDialog from '@/components/BatchEditDeviceDialog.vue'
import type { BatchEditMode } from '@/components/BatchEditDeviceDialog.vue'
import DevicePanelPreview from '@/components/DevicePanelPreview.vue'
import RackCabinet from '@/components/RackCabinet.vue'
import RackRangePicker from '@/components/RackRangePicker.vue'
import { useAuthStore } from '@/stores/auth'
import type { PortLayout } from '@/api/network'
import { resolveDeviceTypeByInfer } from '@/utils/batchMountTypeLimits'
import {
  DEVICE_TYPE_CODES,
  DEVICE_TYPE_FALLBACK_NAMES,
  RESOURCE_CLASS_LABELS,
  buildDeviceTypeOptions,
  displayDeviceTypeName,
  isDeviceTypeCode,
  resourceClassOf,
  type DeviceTypeCode,
  type ResourceClass,
} from '@/utils/deviceTypeCatalog'

const auth = useAuthStore()
const route = useRoute()
const activeTab = ref<'devices' | 'profiles' | 'ips'>('devices')
const profileSubTab = ref<'bmc' | 'system' | 'type' | 'model'>('bmc')

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

const selectedFormContract = computed(
  () => formContracts.value.find((c) => c.id === form.contract_id) || null,
)

const formContractItems = computed((): DeviceContractItem[] => {
  const items = selectedFormContract.value?.device_items
  return Array.isArray(items)
    ? items.filter((it) => {
        if (!it.device_name) return false
        const kind = it.item_kind || 'hardware'
        return kind !== 'software'
      })
    : []
})

function contractItemOptionLabel(it: DeviceContractItem) {
  const name = (it.device_name || '').trim()
  const model = (it.device_model_name || '').trim()
  const mfg = (it.manufacturer_name || '').trim()
  if (model && mfg) return `${name} · ${model} · ${mfg}`
  if (model) return `${name} · ${model}`
  return name
}

function findModelForContract(
  modelName: string,
  mfg: Manufacturer | null,
  source: DeviceModel[] = models.value,
): DeviceModel | undefined {
  const name = modelName.trim()
  if (!name) return undefined
  const lower = name.toLowerCase()
  const byName = source.filter(
    (m) => m.name.toLowerCase() === lower || m.code.toLowerCase() === lower,
  )
  if (!byName.length) return undefined
  if (mfg) {
    const withMfg = byName.find(
      (m) => m.manufacturer_id === mfg.id || m.manufacturer_name === mfg.name,
    )
    if (withMfg) return withMfg
  }
  return byName[0]
}

async function onFormContractChange(contractId: string | null) {
  form.contract_id = contractId || null
  form.contract_item_key = ''
  form.manufacturer_id = null
  if (!contractId) {
    form.project_scope = ''
    return
  }
  const contract = formContracts.value.find((c) => c.id === contractId)
  if (contract?.project_no) {
    form.project_scope = contract.project_no
  }
  try {
    // 先按合同同步型号档案，再自动关联合同设备
    await syncContractModelsById(contractId)
    await Promise.all([loadProfileRefs(), loadManufacturers()])
  } catch {
    /* 同步失败仍尝试本地匹配 */
  }
  const items = formContractItems.value
  if (items.length === 1) {
    await onFormContractItemChange(contractItemKey(items[0]))
  }
}

async function onFormContractItemChange(key: string | null) {
  form.contract_item_key = key || ''
  const item = findContractItem(selectedFormContract.value, key)
  if (!item) {
    form.manufacturer_id = null
    return
  }
  form.name = item.device_name
  if (!form.hostname) form.hostname = item.device_name
  try {
    const mfg = await ensureManufacturer(item.manufacturer_name)
    form.manufacturer_id = mfg?.id || null
    const modelName = (item.device_model_name || item.device_name || '').trim()
    if (!modelName) {
      ElMessage.warning('该合同设备未填写型号，请手动选择产品型号')
      applyInferredMountType(item.device_name, form.hostname)
      return
    }
    let hit = findModelForContract(modelName, mfg)
    if (!hit) {
      const id = await ensureDeviceModel(modelName, {
        height_u: form.height_u,
        power: form.power,
        manufacturer_id: mfg?.id || null,
      })
      hit = models.value.find((m) => m.id === id)
    }
    if (hit) {
      form.device_model_id = hit.id
      form.height_u = hit.height_u
      form.power = hit.power
      if (!form.manufacturer_id && hit.manufacturer_id) {
        form.manufacturer_id = hit.manufacturer_id
      }
      applyInferredMountType(item.device_name, hit.name, hit.code, form.hostname)
    }
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '匹配合同厂商/型号失败')
  }
}

const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const keyword = ref('')

const ipLoading = ref(false)
const ipSegmentTable = ref<IpSegment[]>([])
const ipSegmentPagination = reactive({ page: 1, page_size: 20, total: 0 })
const ipKeyword = ref('')
const ipAppTypeFilter = ref('')
const ipBatchBusy = ref(false)

const selectedIps = ref<IpAddress[]>([])
const ipDetailVisible = ref(false)
const ipDetailLoading = ref(false)
const ipDetailAddressesLoading = ref(false)
const ipDetail = ref<IpSegmentDetail | null>(null)

const IP_STATUS_OPTIONS: Array<{ value: IpStatus; label: string; type: 'success' | 'warning' | 'info' | 'danger' }> = [
  { value: 'free', label: '空闲', type: 'success' },
  { value: 'allocated', label: '已分配', type: 'warning' },
  { value: 'reserved', label: '保留', type: 'info' },
  { value: 'disabled', label: '已禁用', type: 'danger' },
]

const IP_PURPOSE_OPTIONS = [
  { value: '业务地址', label: '业务地址' },
  { value: '管理地址', label: '管理地址' },
  { value: '存储地址', label: '存储地址' },
  { value: 'BMC地址', label: 'BMC地址' },
  { value: '备份地址', label: '备份地址' },
]

const IP_NETWORK_TYPE_OPTIONS = [
  { value: '互联网', label: '互联网' },
  { value: '内网', label: '内网' },
  { value: '专网', label: '专网' },
]

/** 机房在地址段「所属机房位置」中的展示文案 */
function roomLocationLabel(room: Room): string {
  const parts = [
    room.datacenter_name,
    room.building_no ? `${room.building_no}号楼` : null,
    room.room_no || null,
    room.name || null,
  ].filter((x): x is string => Boolean(x && String(x).trim()))
  const unique = [...new Set(parts)]
  return unique.join(' · ') || room.name || room.id
}

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
  application: '',
  network: '',
  prefix_len: 24,
  gateway: '',
  reserved_ips: '',
  address_purpose: '业务地址',
  network_type: '互联网',
  location: '',
  remarks: '',
  dns: '',
  dns_secondary: '',
})

const ipSegmentEditVisible = ref(false)
const ipSegmentEditingId = ref<string | null>(null)
const ipSegmentEditForm = reactive({
  application: '',
  gateway: '',
  address_purpose: '',
  network_type: '',
  location: '',
  remarks: '',
  dns: '',
  dns_secondary: '',
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
const editingPanel = ref<{
  port_layout: PortLayout | Record<string, unknown> | null
  network_kind: string | null
  device_name: string | null
} | null>(null)
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
  /** 合同明细键：kind||name||model||mfg */
  contract_item_key: '' as string,
  manufacturer_id: null as string | null,
  height_u: 1 as number | null,
  power: null as number | null,
  warranty_years: null as number | null,
  project_scope: '',
  project_app: '',
  mounted_at: null as string | null,
  description: '',
  room_id: '',
  rack_id: '',
  u_position: 1 as number | null,
  system_segment_id: '' as string,
  system_ip_id: '' as string | null,
  bmc_segment_id: '' as string,
  bmc_ip_id: '' as string | null,
  vip_segment_id: '' as string,
  vip_ip_id: '' as string | null,
})

/** 设备类型（上架选型）固定清单；类型归类由其自动推导 */
const deviceTypeOptions = computed(() => buildDeviceTypeOptions(types.value))

const resourceClassLabel = computed(() => {
  const t = types.value.find((x) => x.id === form.device_type_id)
  const code =
    t?.code
    || deviceTypeOptions.value.find((o) => o.id === form.device_type_id)?.code
    || null
  return RESOURCE_CLASS_LABELS[resourceClassOf(code)]
})

const resourceClassKey = computed(() => {
  const t = types.value.find((x) => x.id === form.device_type_id)
  const code =
    t?.code
    || deviceTypeOptions.value.find((o) => o.id === form.device_type_id)?.code
    || null
  return resourceClassOf(code)
})

async function ensureDeviceTypeOption(code: DeviceTypeCode) {
  const existed = types.value.find((t) => t.code === code)
  if (existed) return existed
  const created = await createDeviceType({
    code,
    name: DEVICE_TYPE_FALLBACK_NAMES[code],
    description: DEVICE_TYPE_FALLBACK_NAMES[code],
  })
  types.value = [...types.value, created].sort((a, b) => a.code.localeCompare(b.code))
  return created
}

async function onDeviceTypePick(typeId: string | null) {
  if (!typeId) {
    form.device_type_id = null
    return
  }
  const opt = deviceTypeOptions.value.find((o) => o.id === typeId || o.code === typeId)
  if (opt?.missing) {
    const created = await ensureDeviceTypeOption(opt.code)
    form.device_type_id = created.id
    return
  }
  form.device_type_id = typeId
}

function applyInferredMountType(...parts: Array<string | null | undefined>) {
  const hit = resolveDeviceTypeByInfer(types.value, ...parts)
  if (!hit) return
  // 仅接受清单内类型；否则按名称再匹配兜底显示名
  if (isDeviceTypeCode(hit.code)) {
    form.device_type_id = hit.id
    return
  }
  const byName = deviceTypeOptions.value.find((o) => o.name === hit.name)
  if (byName?.id) form.device_type_id = byName.id
}

function onFormRoomChange() {
  form.rack_id = ''
  formLayoutSlots.value = []
  formLayoutTotalPower.value = 0
}

function deviceTypeCodeOf(row: Device): string | null {
  return (
    row.device_type_code
    || types.value.find((t) => t.id === row.device_type_id)?.code
    || null
  )
}

function deviceTypeDisplayName(row: Device): string {
  return displayDeviceTypeName(types.value, row.device_type_id || row.device_type_code, row.device_type_name)
}

function deviceResourceClassOf(row: Device): ResourceClass {
  return resourceClassOf(deviceTypeCodeOf(row))
}

function deviceResourceClassLabel(row: Device): string {
  return RESOURCE_CLASS_LABELS[deviceResourceClassOf(row)]
}

function locationText(row: Device): string {
  if (!row.rack_id) return '—'
  return `${row.room_name || '—'} / ${row.rack_code || '—'} / U${row.u_position ?? '—'}`
}

const paramViewVisible = ref(false)
const paramViewLoading = ref(false)
const paramViewDevice = ref<Device | null>(null)
const paramViewProfile = ref<ParamProfile | null>(null)

function normalizeParamName(s: string | null | undefined) {
  return (s || '').trim().toLowerCase()
}

function findContractParamByName(name: string | null | undefined, pool: ParamProfile[]) {
  const key = normalizeParamName(name)
  if (!key) return null
  return (
    pool.find(
      (p) =>
        normalizeParamName(p.name) === key
        || normalizeParamName(p.source_device_name) === key
        || normalizeParamName(p.payload?.source_device_name) === key,
    ) || null
  )
}

function formatDiskSpec(d: {
  size_gb?: number | null
  count?: number | null
  interface?: string | null
  media_type?: string | null
} | null | undefined) {
  if (!d) return '—'
  const mediaMap: Record<string, string> = { ssd: 'SSD', hdd: '机械盘', nvme: 'NVMe' }
  const bits = [
    d.size_gb != null ? `${d.size_gb}GB` : '',
    d.count != null ? `×${d.count}块` : '',
    d.interface || '',
    d.media_type ? mediaMap[d.media_type] || d.media_type : '',
  ].filter(Boolean)
  return bits.length ? bits.join(' ') : '—'
}

function paramViewDisks(role: 'system' | 'data') {
  const disks = paramViewProfile.value?.payload?.disks || []
  const hasRole = disks.some((d) => d.role)
  if (hasRole) {
    return disks.filter((d) => d.role === role)
  }
  if (role === 'system') return disks[0] ? [disks[0]] : []
  return disks.slice(1)
}

function paramViewTypeName(p: ParamProfile | null) {
  if (!p) return '—'
  const typeId = p.device_type_id || p.payload?.device_type_id
  if (!typeId) return '—'
  const hit = types.value.find((t) => t.id === typeId)
  return hit?.name || '—'
}

function paramViewTypeClass(p: ParamProfile | null) {
  if (!p) return '—'
  const typeId = p.device_type_id || p.payload?.device_type_id
  if (!typeId) return '—'
  const hit = types.value.find((t) => t.id === typeId)
  const code = hit?.code || ''
  if (!code) return '—'
  return RESOURCE_CLASS_LABELS[resourceClassOf(code)] || '—'
}

function paramViewOtherText(p: ParamProfile | null) {
  if (!p) return ''
  const payload = p.payload
  if (p.other_params?.trim()) return p.other_params
  if (payload?.other_params?.trim()) return payload.other_params
  if (!payload) return ''
  const lines: string[] = []
  const fanBits = [
    payload.fan_count != null ? `${payload.fan_count}个` : '',
    payload.fan_model || '',
  ].filter(Boolean)
  if (fanBits.length) lines.push(`风扇: ${fanBits.join(' ')}`)
  if (payload.psu_power_w != null) lines.push(`电源: ${payload.psu_power_w}W`)
  const raidBits = [payload.raid?.model || '', payload.raid?.params || ''].filter(Boolean)
  if (raidBits.length) lines.push(`RAID: ${raidBits.join(' / ')}`)
  if (payload.supported_os?.length) lines.push(`操作系统: ${payload.supported_os.join(', ')}`)
  return lines.join('\n')
}

async function resolveContractParamProfile(row: Device): Promise<ParamProfile | null> {
  let pool = paramProfiles.value
  if (!pool.length) {
    pool = await listParamProfiles()
    paramProfiles.value = pool
  }

  // 1) 已绑定参数档案 → 取其名称再对齐合同设备参数（同名）
  let linked: ParamProfile | null = null
  if (row.param_profile_id) {
    linked = pool.find((p) => p.id === row.param_profile_id) || null
  }

  const nameCandidates = [
    linked?.name,
    linked?.source_device_name,
    linked?.payload?.source_device_name,
    row.name,
  ].filter(Boolean) as string[]

  for (const name of nameCandidates) {
    const hit = findContractParamByName(name, pool)
    if (hit) return hit
  }

  // 2) 按采购名称关键字从合同设备参数接口再查一次
  const keyword = (row.name || linked?.name || '').trim()
  if (keyword) {
    try {
      const remote = await listParamProfiles({ keyword, page_size: 200 })
      for (const name of [keyword, ...nameCandidates]) {
        const hit = findContractParamByName(name, remote)
        if (hit) {
          // 合并进本地缓存
          const map = new Map(paramProfiles.value.map((p) => [p.id, p]))
          for (const item of remote) map.set(item.id, item)
          paramProfiles.value = [...map.values()]
          return hit
        }
      }
    } catch {
      // ignore
    }
  }

  // 3) 回退：直接展示已绑定档案
  return linked
}

async function viewDeviceParams(row: Device) {
  paramViewDevice.value = row
  paramViewProfile.value = null
  paramViewVisible.value = true
  paramViewLoading.value = true
  try {
    const profile = await resolveContractParamProfile(row)
    if (!profile) {
      paramViewVisible.value = false
      ElMessage.warning(
        row.name
          ? `未在合同设备参数中找到与「${row.name}」对应的参数，请先在合同-设备参数中完善或绑定`
          : '该设备未关联设备参数，且无采购名称可匹配合同参数',
      )
      return
    }
    paramViewProfile.value = profile
  } catch (error: unknown) {
    paramViewVisible.value = false
    const err = error as { message?: string }
    ElMessage.error(err.message || '加载合同设备参数失败')
  } finally {
    paramViewLoading.value = false
  }
}

const formRoomMeta = computed(() => rooms.value.find((r) => r.id === form.room_id) || null)
const formDatacenterLabel = computed(() => {
  const r = formRoomMeta.value
  if (!r) return ''
  return r.datacenter_name || '—'
})

const deviceIpSegments = ref<IpSegment[]>([])
const systemIpOptions = ref<IpAddress[]>([])
const bmcIpOptions = ref<IpAddress[]>([])
const vipIpOptions = ref<IpAddress[]>([])
const ipOptionsLoading = reactive({
  system: false,
  bmc: false,
  vip: false,
})
const ipAssignHydrating = ref(false)

async function ensureDeviceIpSegments() {
  if (deviceIpSegments.value.length) return
  try {
    const data = await listIpSegments({ page: 1, page_size: 200 })
    deviceIpSegments.value = data?.items ?? []
  } catch {
    deviceIpSegments.value = []
  }
}

function sortIpOptions(items: IpAddress[]) {
  return [...items].sort((a, b) => {
    const aa = a.system_ip.split('.').map(Number)
    const bb = b.system_ip.split('.').map(Number)
    for (let i = 0; i < 4; i += 1) {
      if ((aa[i] || 0) !== (bb[i] || 0)) return (aa[i] || 0) - (bb[i] || 0)
    }
    return 0
  })
}

async function loadSegmentIpOptions(
  kind: 'system' | 'bmc' | 'vip',
  segmentId: string,
  keepIpId?: string | null,
) {
  if (!segmentId) {
    if (kind === 'system') systemIpOptions.value = []
    if (kind === 'bmc') bmcIpOptions.value = []
    if (kind === 'vip') vipIpOptions.value = []
    return
  }
  ipOptionsLoading[kind] = true
  try {
    const params: Record<string, unknown> = {
      page: 1,
      page_size: 200,
      segment_id: segmentId,
    }
    // 业务 / 带外：仅空闲；虚拟 IP：非禁用即可（可复用）
    if (kind === 'system' || kind === 'bmc') {
      params.status = 'free'
    }
    const data = await listIpAddresses(params)
    let items = (data?.items ?? []) as IpAddress[]
    if (kind === 'vip') {
      items = items.filter((ip) => ip.status !== 'disabled')
    }
    // 编辑时保留当前已分配地址，避免下拉中消失
    if (keepIpId && !items.some((ip) => ip.id === keepIpId)) {
      try {
        const mine = await listIpAddresses({
          page: 1,
          page_size: 50,
          segment_id: segmentId,
          ...(kind !== 'vip' && editingId.value ? { device_id: editingId.value } : {}),
        })
        const extra = ((mine?.items ?? []) as IpAddress[]).filter((ip) => ip.id === keepIpId)
        if (!extra.length && kind === 'vip') {
          const all = await listIpAddresses({ page: 1, page_size: 200, segment_id: segmentId })
          items = [
            ...((all?.items ?? []) as IpAddress[]).filter((ip) => ip.id === keepIpId),
            ...items,
          ]
        } else {
          items = [...extra, ...items]
        }
      } catch {
        /* ignore */
      }
    }
    items = sortIpOptions(items)
    if (kind === 'system') systemIpOptions.value = items
    if (kind === 'bmc') bmcIpOptions.value = items
    if (kind === 'vip') vipIpOptions.value = items
  } catch {
    if (kind === 'system') systemIpOptions.value = []
    if (kind === 'bmc') bmcIpOptions.value = []
    if (kind === 'vip') vipIpOptions.value = []
  } finally {
    ipOptionsLoading[kind] = false
  }
}

watch(
  () => form.system_segment_id,
  (id) => {
    if (!ipAssignHydrating.value) form.system_ip_id = null
    void loadSegmentIpOptions('system', id, form.system_ip_id)
  },
)
watch(
  () => form.bmc_segment_id,
  (id) => {
    if (!ipAssignHydrating.value) form.bmc_ip_id = null
    void loadSegmentIpOptions('bmc', id, form.bmc_ip_id)
  },
)
watch(
  () => form.vip_segment_id,
  (id) => {
    if (!ipAssignHydrating.value) form.vip_ip_id = null
    void loadSegmentIpOptions('vip', id, form.vip_ip_id)
  },
)

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
const mountIsMove = ref(false)
const mountForm = reactive({
  device_id: '',
  room_id: '',
  rack_id: '',
  u_position: 1,
})
const mountDialogTitle = computed(() => (mountIsMove.value ? '移动设备' : '手动上架'))
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
const batchEditVisible = ref(false)
const batchEditMode = ref<BatchEditMode>('contract')

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
  source_device_name: '' as string,
  source_device_model: '' as string,
  source_manufacturer: '' as string,
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

function genManufacturerCode(name: string) {
  const ascii = name
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 40)
  const base = ascii ? `MFG_${ascii}` : `MFG_${Date.now().toString(36).toUpperCase()}`
  return base.slice(0, 50)
}

async function ensureManufacturer(name: string | null | undefined): Promise<Manufacturer | null> {
  const trimmed = (name || '').trim()
  if (!trimmed) return null
  const hit = manufacturers.value.find((m) => m.name === trimmed || m.code === trimmed)
  if (hit) return hit
  let code = genManufacturerCode(trimmed)
  if (manufacturers.value.some((m) => m.code === code)) {
    code = `${code}_${Date.now().toString(36).toUpperCase()}`.slice(0, 50)
  }
  const created = await createManufacturer({
    code,
    name: trimmed,
    description: '来自合同信息同步',
  })
  manufacturers.value = [...manufacturers.value, created].sort((a, b) =>
    a.name.localeCompare(b.name),
  )
  return created
}

async function loadManufacturers() {
  manufacturers.value = await listManufacturers()
}

async function syncModelsFromContracts(options?: { quiet?: boolean }) {
  if (!auth.hasPermission('device:create')) return null
  const result = await syncContractModels()
  if (result.created > 0 || result.deleted > 0) {
    await loadProfileRefs()
    await loadManufacturers()
  }
  if (!options?.quiet) {
    const parts: string[] = []
    if (result.created > 0) parts.push(`新建 ${result.created} 个型号`)
    if (result.deleted > 0) parts.push(`清理 ${result.deleted} 个无合同引用型号`)
    if (result.kept_in_use > 0) parts.push(`${result.kept_in_use} 个仍有设备使用已保留`)
    if (parts.length) {
      ElMessage.success(`合同型号同步完成：${parts.join('，')}`)
    } else {
      ElMessage.info('合同中的产品型号均已存在，无需同步')
    }
  }
  return result
}

async function handleSyncModelsFromContracts() {
  syncModelsLoading.value = true
  try {
    await loadLocationRefs()
    await syncModelsFromContracts()
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
  opts?: {
    height_u?: number | null
    power?: number | null
    manufacturer_id?: string | null
  },
): Promise<string | null> {
  if (!value) return null
  if (models.value.some((m) => m.id === value)) return value
  const name = value.trim()
  if (!name) return null
  const mfgId = opts?.manufacturer_id ?? form.manufacturer_id ?? null
  const byName =
    models.value.find(
      (m) =>
        (m.name === name || m.code === name)
        && (!mfgId || m.manufacturer_id === mfgId),
    ) || models.value.find((m) => m.name === name || m.code === name)
  if (byName) return byName.id
  let code = genModelCode(name)
  if (models.value.some((m) => m.code === code)) {
    code = `${code}_${Date.now().toString(36).toUpperCase()}`.slice(0, 50)
  }
  const created = await createDeviceModel({
    code,
    name,
    manufacturer_id: mfgId,
    height_u: opts?.height_u || form.height_u || 1,
    power: opts?.power ?? form.power ?? null,
    description: null,
  })
  models.value = [...models.value, created].sort((a, b) => a.name.localeCompare(b.name))
  if (created.manufacturer_id && !form.manufacturer_id) {
    form.manufacturer_id = created.manufacturer_id
  }
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
      // 仅在未指定设备级厂商时，用型号厂商预填
      if (!form.manufacturer_id && model.manufacturer_id) {
        form.manufacturer_id = model.manufacturer_id
      }
      applyInferredMountType(model.name, model.code, form.name, form.hostname)
    }
  } catch (error: unknown) {
    form.device_model_id = ''
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '创建型号失败')
  }
}

async function onManufacturerChange(value: string | null) {
  try {
    if (!value) {
      form.manufacturer_id = null
      return
    }
    if (manufacturers.value.some((m) => m.id === value)) {
      form.manufacturer_id = value
      return
    }
    const mfg = await ensureManufacturer(value)
    form.manufacturer_id = mfg?.id || null
  } catch (error: unknown) {
    form.manufacturer_id = null
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '保存厂商失败')
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
        manufacturer_id: form.manufacturer_id,
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

function emptyDisk(role: DiskRole | null = null): ParamDiskSpec {
  return { size_gb: null, count: null, interface: null, media_type: null, role }
}

function defaultDiskRows(count = DEFAULT_DISK_SPEC_COUNT): ParamDiskSpec[] {
  return Array.from({ length: count }, (_, i) => emptyDisk(i === 0 ? 'system' : 'data'))
}

function isDiskRowFilled(d: ParamDiskSpec): boolean {
  return d.size_gb != null || d.count != null || !!d.interface || !!d.media_type
}

function resetParamForm() {
  paramForm.code = ''
  paramForm.name = ''
  paramForm.description = ''
  paramForm.source_device_name = ''
  paramForm.source_device_model = ''
  paramForm.source_manufacturer = ''
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
  paramForm.source_device_name = p.source_device_name || row.source_device_name || row.name || ''
  paramForm.source_device_model = p.source_device_model || row.source_device_model || ''
  paramForm.source_manufacturer = p.source_manufacturer || row.source_manufacturer || ''
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
        role: d.role ?? null,
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
    source_device_name: paramForm.source_device_name || paramForm.name || null,
    source_device_model: paramForm.source_device_model || null,
    source_manufacturer: paramForm.source_manufacturer || null,
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
        role: d.role || null,
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
  mounted: '上架加电',
  mounted_nopower: '上架无电',
  app_online: '应用上线',
  app_offline: '应用下线',
  fault: '故障',
  maintenance: '维护',
  retired: '退役',
}

/** 修改状态可选值；上架加电 / 下架 / 库存走现有上架、下架流程 */
type DeviceStatusAction =
  | 'mounted'
  | 'mounted_nopower'
  | 'app_online'
  | 'app_offline'
  | 'unmount'
  | 'stock'
  | 'fault'

const DEVICE_STATUS_OPTIONS: { value: DeviceStatusAction; label: string; hint: string }[] = [
  { value: 'mounted', label: '上架加电', hint: '未上架时打开上架对话框；已上架则直接改状态' },
  { value: 'mounted_nopower', label: '上架无电', hint: '需已上架' },
  { value: 'app_online', label: '应用上线', hint: '需已上架' },
  { value: 'app_offline', label: '应用下线', hint: '需已上架' },
  { value: 'unmount', label: '下架', hint: '沿用现有下架确认' },
  { value: 'stock', label: '库存', hint: '未上架直接设为库存；已上架则先下架' },
  { value: 'fault', label: '故障', hint: '可直接设置' },
]

const statusChangeVisible = ref(false)
const statusChangeSaving = ref(false)
const statusChangeDevice = ref<Device | null>(null)
const statusChangeTarget = ref<DeviceStatusAction>('mounted')

function openStatusChange(row: Device) {
  statusChangeDevice.value = row
  const current = row.status as DeviceStatusAction
  const known = DEVICE_STATUS_OPTIONS.some((o) => o.value === current)
  statusChangeTarget.value = known ? current : row.rack_id ? 'mounted' : 'stock'
  statusChangeVisible.value = true
}

async function handleStatusChangeConfirm() {
  const row = statusChangeDevice.value
  if (!row) return
  const target = statusChangeTarget.value

  if (target === 'mounted') {
    if (!row.rack_id) {
      statusChangeVisible.value = false
      openMount(row)
      return
    }
    statusChangeSaving.value = true
    try {
      await updateDevice(row.id, { status: 'mounted' })
      ElMessage.success('状态已更新为「上架加电」')
      statusChangeVisible.value = false
      await loadData()
    } catch (error: unknown) {
      const err = error as { response?: { data?: { message?: string } }; message?: string }
      ElMessage.error(err.response?.data?.message || err.message || '修改失败')
    } finally {
      statusChangeSaving.value = false
    }
    return
  }
  if (target === 'unmount') {
    if (!row.rack_id) {
      ElMessage.warning('设备未上架，无需下架')
      return
    }
    statusChangeVisible.value = false
    await handleUnmount(row)
    return
  }
  if (target === 'stock') {
    if (row.rack_id) {
      statusChangeVisible.value = false
      await handleUnmount(row)
      return
    }
    if (row.status === 'stock') {
      ElMessage.info('设备已是库存状态')
      statusChangeVisible.value = false
      return
    }
    statusChangeSaving.value = true
    try {
      await updateDevice(row.id, { status: 'stock' })
      ElMessage.success('已设为库存')
      statusChangeVisible.value = false
      await loadData()
    } catch (error: unknown) {
      const err = error as { response?: { data?: { message?: string } }; message?: string }
      ElMessage.error(err.response?.data?.message || err.message || '修改失败')
    } finally {
      statusChangeSaving.value = false
    }
    return
  }

  const onRackStatuses = new Set(['mounted_nopower', 'app_online', 'app_offline'])
  if (onRackStatuses.has(target) && !row.rack_id) {
    ElMessage.warning('请先上架设备后再设置该状态')
    return
  }

  statusChangeSaving.value = true
  try {
    await updateDevice(row.id, { status: target })
    ElMessage.success(`状态已更新为「${statusLabel[target] || target}」`)
    statusChangeVisible.value = false
    await loadData()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '修改失败')
  } finally {
    statusChangeSaving.value = false
  }
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
  void syncCanonicalDeviceTypeNames()
}

/** 将库中旧短名（计算/存储/安全）同步为标准展示名，并补齐「其他」 */
async function syncCanonicalDeviceTypeNames() {
  const byCode = new Map(types.value.map((t) => [t.code, t]))
  for (const code of DEVICE_TYPE_CODES) {
    const want = DEVICE_TYPE_FALLBACK_NAMES[code]
    const hit = byCode.get(code)
    if (!hit) {
      try {
        const created = await createDeviceType({ code, name: want, description: want })
        types.value = [...types.value, created]
        byCode.set(code, created)
      } catch {
        // ignore create race / permission
      }
      continue
    }
    if (hit.name !== want) {
      try {
        const updated = await updateDeviceType(hit.id, { name: want, description: want })
        types.value = types.value.map((t) => (t.id === updated.id ? updated : t))
        byCode.set(code, updated)
      } catch {
        // ignore
      }
    }
  }
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
    const data = await listIpSegments({
      page: ipSegmentPagination.page,
      page_size: ipSegmentPagination.page_size,
      keyword: ipKeyword.value || undefined,
      address_purpose: ipAppTypeFilter.value || undefined,
    })
    ipSegmentTable.value = data.items
    ipSegmentPagination.total = data.pagination.total
  } catch {
    ipSegmentTable.value = []
    ElMessage.error('加载地址段失败')
  } finally {
    ipLoading.value = false
  }
}

async function loadSegmentAddresses(segmentId: string): Promise<IpAddress[]> {
  const pages: IpAddress[] = []
  let page = 1
  let total = 0
  do {
    const data = await listIpAddresses({
      page,
      page_size: 200,
      segment_id: segmentId,
    })
    pages.push(...(data.items || []))
    total = data.pagination?.total ?? pages.length
    page += 1
  } while (pages.length < total && page <= 50)
  return pages
}

async function openIpSegmentDetail(row: IpSegment) {
  ipDetailVisible.value = true
  ipDetailLoading.value = true
  ipDetailAddressesLoading.value = false
  selectedIps.value = []
  try {
    // 先拉段信息（不含全量地址），对话框秒开；地址分页加载避免卡顿
    const meta = await getIpSegment(row.id, { include_addresses: false })
    ipDetail.value = { ...meta, addresses: [] }
    ipDetailLoading.value = false
    ipDetailAddressesLoading.value = true
    const addresses = await loadSegmentAddresses(row.id)
    if (ipDetail.value?.id === row.id) {
      ipDetail.value = { ...ipDetail.value, addresses }
    }
  } catch (error: unknown) {
    ipDetail.value = null
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '加载地址段详情失败')
    ipDetailLoading.value = false
  } finally {
    ipDetailAddressesLoading.value = false
  }
}

async function refreshIpDetail() {
  if (!ipDetail.value) return
  const segmentId = ipDetail.value.id
  ipDetailLoading.value = true
  ipDetailAddressesLoading.value = true
  try {
    const meta = await getIpSegment(segmentId, { include_addresses: false })
    const addresses = await loadSegmentAddresses(segmentId)
    if (ipDetail.value?.id === segmentId) {
      ipDetail.value = { ...meta, addresses }
    }
    selectedIps.value = []
  } finally {
    ipDetailLoading.value = false
    ipDetailAddressesLoading.value = false
  }
}

/** 设备删除/下架后刷新地址段列表与详情，使释放后的 IP 立刻可见 */
async function refreshIpAfterDeviceChange() {
  try {
    await loadIpData()
  } catch {
    /* ignore */
  }
  if (ipDetailVisible.value) {
    try {
      await refreshIpDetail()
    } catch {
      /* ignore */
    }
  }
}

async function handleIpSegmentDelete(row: IpSegment) {
  await ElMessageBox.confirm(
    `确定删除地址段「${row.name}」及其全部 ${row.total_count} 个地址吗？`,
    '删除地址段',
    { type: 'warning' },
  )
  await deleteIpSegment(row.id)
  ElMessage.success('地址段已删除')
  if (ipDetail.value?.id === row.id) {
    ipDetailVisible.value = false
    ipDetail.value = null
  }
  await loadIpData()
}

function openIpSegmentEdit(row?: IpSegment | null) {
  const seg = row || ipDetail.value
  if (!seg) return
  ipSegmentEditingId.value = seg.id
  ipSegmentEditForm.application = seg.application || ''
  ipSegmentEditForm.gateway = seg.gateway || ''
  ipSegmentEditForm.address_purpose = seg.address_purpose || ''
  ipSegmentEditForm.network_type = seg.network_type || ''
  ipSegmentEditForm.location = seg.location || ''
  ipSegmentEditForm.remarks = seg.remarks || ''
  ipSegmentEditForm.dns = seg.dns || ''
  ipSegmentEditForm.dns_secondary = seg.dns_secondary || ''
  ipSegmentEditVisible.value = true
  void loadLocationRefs().catch(() => undefined)
}

async function saveIpSegmentEdit() {
  const id = ipSegmentEditingId.value || ipDetail.value?.id
  if (!id) return
  try {
    const updated = await updateIpSegment(id, {
      application: ipSegmentEditForm.application.trim() || null,
      gateway: ipSegmentEditForm.gateway.trim() || null,
      address_purpose: ipSegmentEditForm.address_purpose.trim() || null,
      network_type: ipSegmentEditForm.network_type.trim() || null,
      location: ipSegmentEditForm.location.trim() || null,
      remarks: ipSegmentEditForm.remarks.trim() || null,
      dns: ipSegmentEditForm.dns.trim() || null,
      dns_secondary: ipSegmentEditForm.dns_secondary.trim() || null,
    })
    if (ipDetail.value?.id === id) {
      ipDetail.value = { ...ipDetail.value, ...updated, addresses: ipDetail.value.addresses }
    }
    ElMessage.success('地址段已更新')
    ipSegmentEditVisible.value = false
    ipSegmentEditingId.value = null
    await loadIpData()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '保存失败')
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
  form.device_type_id = types.value.find((t) => t.code === 'switch_10g')?.id
    || types.value.find((t) => (DEVICE_TYPE_CODES as readonly string[]).includes(t.code))?.id
    || null
  form.param_profile_id = null
  form.bmc_profile_id = null
  form.system_profile_id = null
  form.contract_id = null
  form.contract_item_key = ''
  form.manufacturer_id = null
  form.height_u = 1
  form.power = null
  form.warranty_years = null
  form.project_scope = ''
  form.project_app = ''
  form.mounted_at = null
  form.description = ''
  form.room_id = ''
  form.rack_id = ''
  form.u_position = 1
  form.system_segment_id = ''
  form.system_ip_id = null
  form.bmc_segment_id = ''
  form.bmc_ip_id = null
  form.vip_segment_id = ''
  form.vip_ip_id = null
  systemIpOptions.value = []
  bmcIpOptions.value = []
  vipIpOptions.value = []
  originalMount.value = { rack_id: null, u_position: null }
  formLayoutSlots.value = []
  formLayoutTotalPower.value = 0
}

function openCreate() {
  editingId.value = null
  editingPanel.value = null
  resetForm()
  editVisible.value = true
  void ensureDeviceIpSegments()
}

function applyDeviceIpAssign(detail: Device) {
  ipAssignHydrating.value = true
  form.system_segment_id = detail.system_segment_id || ''
  form.system_ip_id = detail.system_ip_id || null
  form.bmc_segment_id = detail.bmc_segment_id || ''
  form.bmc_ip_id = detail.bmc_ip_id || null
  form.vip_segment_id = detail.vip_segment_id || ''
  form.vip_ip_id = detail.vip_ip_id || null
  void Promise.all([
    form.system_segment_id
      ? loadSegmentIpOptions('system', form.system_segment_id, form.system_ip_id)
      : Promise.resolve(),
    form.bmc_segment_id
      ? loadSegmentIpOptions('bmc', form.bmc_segment_id, form.bmc_ip_id)
      : Promise.resolve(),
    form.vip_segment_id
      ? loadSegmentIpOptions('vip', form.vip_segment_id, form.vip_ip_id)
      : Promise.resolve(),
  ]).finally(() => {
    ipAssignHydrating.value = false
  })
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
  form.contract_item_key = matchContractItemKey(
    contracts.value.find((c) => c.id === row.contract_id) || null,
    row.name,
    row.device_model_name,
  )
  form.manufacturer_id = row.manufacturer_id || null
  form.height_u = row.height_u
  form.power = row.power
  form.warranty_years = row.warranty_years ?? null
  form.project_scope = row.project_scope || row.project_no || ''
  form.project_app = row.project_app || ''
  form.mounted_at = row.mounted_at || null
  form.description = row.description || ''
  form.room_id = row.room_id || ''
  form.rack_id = row.rack_id || ''
  form.u_position = row.u_position || 1
  form.system_segment_id = ''
  form.system_ip_id = null
  form.bmc_segment_id = ''
  form.bmc_ip_id = null
  form.vip_segment_id = ''
  form.vip_ip_id = null
  systemIpOptions.value = []
  bmcIpOptions.value = []
  vipIpOptions.value = []
  originalMount.value = {
    rack_id: row.rack_id || null,
    u_position: row.u_position || null,
  }
  editingPanel.value = {
    port_layout: row.port_layout || null,
    network_kind: row.network_kind || null,
    device_name: row.name || row.hostname,
  }
  editVisible.value = true
  if (form.rack_id) void loadFormRackLayout(form.rack_id)
  void ensureDeviceIpSegments()
  // 列表可能未带全面板/IP 时补拉详情
  void getDevice(row.id)
    .then((d) => {
      if (editingId.value !== row.id) return
      editingPanel.value = {
        port_layout: d.port_layout || null,
        network_kind: d.network_kind || null,
        device_name: d.name || d.hostname,
      }
      form.warranty_years = d.warranty_years ?? form.warranty_years
      form.project_scope = d.project_scope || d.project_no || form.project_scope
      form.project_app = d.project_app || form.project_app
      form.mounted_at = d.mounted_at || form.mounted_at
      applyDeviceIpAssign(d)
    })
    .catch(() => undefined)
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
  if (form.contract_id && !form.contract_item_key) {
    ElMessage.warning('请选择合同内的设备名称，以便采购汇总正确统计已关联数量')
    return
  }
  if (form.vip_ip_id && !form.system_ip_id && !form.bmc_ip_id) {
    ElMessage.warning('分配虚拟IP前请先选择业务地址或带外地址')
    return
  }
  try {
    const payload = {
      name: form.name || form.hostname || form.serial_number,
      hostname: form.hostname || form.name || form.serial_number,
      serial_number: form.serial_number,
      device_model_id: form.device_model_id,
      device_type_id: form.device_type_id || null,
      manufacturer_id: form.manufacturer_id || '',
      param_profile_id: form.param_profile_id || null,
      bmc_profile_id: form.bmc_profile_id || null,
      contract_id: form.contract_id || '',
      system_profile_id: form.system_profile_id || null,
      height_u: form.height_u,
      power: form.power,
      description: form.description || null,
      project_scope: form.project_scope || null,
      project_app: form.project_app || null,
      warranty_years: form.warranty_years,
      mounted_at: form.mounted_at || null,
      system_ip_id: form.system_ip_id || null,
      bmc_ip_id: form.bmc_ip_id || null,
      vip_ip_id: form.vip_ip_id || null,
    }
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
    await refreshIpAfterDeviceChange()
  } catch (error: unknown) {
    const err = error as {
      response?: { data?: { message?: string; details?: { detail?: string } } }
      message?: string
    }
    ElMessage.error(
      err.response?.data?.details?.detail
        || err.response?.data?.message
        || err.message
        || '保存失败，请检查位置或参数是否正确',
    )
  }
}

function isMessageBoxCancel(error: unknown): boolean {
  return error === 'cancel' || error === 'close'
}

async function handleDelete(row: Device) {
  const mountedHint = row.rack_id ? '设备仍在机柜中，将先下架再删除；' : ''
  try {
    await ElMessageBox.confirm(
      `确定删除设备「${row.name || row.hostname}」吗？${mountedHint}已分配的 IP 将释放为空闲。`,
      '确认删除',
      { type: 'warning' },
    )
    await deleteDevice(row.id)
    ElMessage.success('删除成功，已释放关联 IP')
    await loadData()
    await refreshIpAfterDeviceChange()
  } catch (error: unknown) {
    if (isMessageBoxCancel(error)) return
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '删除失败')
  }
}

async function handleBatchDelete() {
  if (!selectedDevices.value.length) return
  const mountedCount = selectedDevices.value.filter((d) => d.rack_id).length
  const mountedHint =
    mountedCount > 0 ? `其中 ${mountedCount} 台仍在机柜中，将先下架再删除；` : ''
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedDevices.value.length} 台设备吗？${mountedHint}已分配的 IP 将释放为空闲。`,
      '批量删除',
      { type: 'warning' },
    )
  } catch (error: unknown) {
    if (isMessageBoxCancel(error)) return
    throw error
  }
  batchBusy.value = true
  try {
    const result = await batchDeleteDevices(selectedDevices.value.map((d) => d.id))
    ElMessage.success(`删除 ${result.deleted} 台，跳过 ${result.skipped} 台（已释放关联 IP）`)
    if (result.errors.length) ElMessage.warning(result.errors.slice(0, 3).join('; '))
    await loadData()
    await refreshIpAfterDeviceChange()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '批量删除失败')
  } finally {
    batchBusy.value = false
  }
}

function openBatchEdit(mode: BatchEditMode) {
  if (!selectedDevices.value.length) {
    ElMessage.warning('请先选择设备')
    return
  }
  batchEditMode.value = mode
  batchEditVisible.value = true
}

const BATCH_EDIT_COMMANDS: BatchEditMode[] = [
  'contract',
  'type',
  'model',
  'manufacturer',
  'unmount',
  'mount',
  'ip',
]

function handleBatchCommand(command: string) {
  if (command === 'delete') {
    void handleBatchDelete()
    return
  }
  if ((BATCH_EDIT_COMMANDS as string[]).includes(command)) {
    openBatchEdit(command as BatchEditMode)
  }
}

async function onBatchEditSuccess() {
  selectedDevices.value = []
  await loadData()
  await refreshIpAfterDeviceChange()
}

function openMount(row: Device) {
  mountIsMove.value = !!row.rack_id
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
    ElMessage.success(mountIsMove.value ? '移动成功' : '上架成功')
    mountVisible.value = false
    await loadData()
  } catch {
    ElMessage.error(mountIsMove.value ? '移动失败，U 位冲突或参数错误' : '上架失败，U 位冲突或参数错误')
  }
}

async function handleUnmount(row: Device) {
  try {
    await ElMessageBox.confirm(
      `确定下架「${row.name || row.hostname}」吗？已分配的 IP 将释放为空闲。`,
      '确认下架',
      { type: 'warning' },
    )
  } catch (error: unknown) {
    if (isMessageBoxCancel(error)) return
    throw error
  }
  try {
    await unmountDevice(row.id)
    ElMessage.success('下架成功，已释放关联 IP')
    await loadData()
    await refreshIpAfterDeviceChange()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '下架失败')
  }
}

const assignIpVisible = ref(false)
const assignIpSaving = ref(false)
const assignIpHydrating = ref(false)
const assignIpDevice = ref<Device | null>(null)
const assignIpForm = reactive({
  system_segment_id: '' as string,
  system_ip_id: null as string | null,
  bmc_segment_id: '' as string,
  bmc_ip_id: null as string | null,
  vip_segment_id: '' as string,
  vip_ip_id: null as string | null,
})
const assignSystemIpOptions = ref<IpAddress[]>([])
const assignBmcIpOptions = ref<IpAddress[]>([])
const assignVipIpOptions = ref<IpAddress[]>([])
const assignIpLoading = reactive({
  system: false,
  bmc: false,
  vip: false,
})

async function loadAssignSegmentIpOptions(
  kind: 'system' | 'bmc' | 'vip',
  segmentId: string,
  keepIpId?: string | null,
) {
  if (!segmentId) {
    if (kind === 'system') assignSystemIpOptions.value = []
    if (kind === 'bmc') assignBmcIpOptions.value = []
    if (kind === 'vip') assignVipIpOptions.value = []
    return
  }
  assignIpLoading[kind] = true
  try {
    const params: Record<string, unknown> = {
      page: 1,
      page_size: 200,
      segment_id: segmentId,
    }
    if (kind === 'system' || kind === 'bmc') {
      params.status = 'free'
    }
    const data = await listIpAddresses(params)
    let items = (data?.items ?? []) as IpAddress[]
    if (kind === 'vip') {
      items = items.filter((ip) => ip.status !== 'disabled')
    }
    const deviceId = assignIpDevice.value?.id
    if (keepIpId && !items.some((ip) => ip.id === keepIpId)) {
      try {
        const mine = await listIpAddresses({
          page: 1,
          page_size: 50,
          segment_id: segmentId,
          ...(kind !== 'vip' && deviceId ? { device_id: deviceId } : {}),
        })
        const extra = ((mine?.items ?? []) as IpAddress[]).filter((ip) => ip.id === keepIpId)
        if (!extra.length && kind === 'vip') {
          const all = await listIpAddresses({ page: 1, page_size: 200, segment_id: segmentId })
          items = [
            ...((all?.items ?? []) as IpAddress[]).filter((ip) => ip.id === keepIpId),
            ...items,
          ]
        } else {
          items = [...extra, ...items]
        }
      } catch {
        /* ignore */
      }
    }
    items = sortIpOptions(items)
    if (kind === 'system') assignSystemIpOptions.value = items
    if (kind === 'bmc') assignBmcIpOptions.value = items
    if (kind === 'vip') assignVipIpOptions.value = items
  } catch {
    if (kind === 'system') assignSystemIpOptions.value = []
    if (kind === 'bmc') assignBmcIpOptions.value = []
    if (kind === 'vip') assignVipIpOptions.value = []
  } finally {
    assignIpLoading[kind] = false
  }
}

watch(
  () => assignIpForm.system_segment_id,
  (id) => {
    if (!assignIpVisible.value) return
    if (!assignIpHydrating.value) assignIpForm.system_ip_id = null
    void loadAssignSegmentIpOptions('system', id, assignIpForm.system_ip_id)
  },
)
watch(
  () => assignIpForm.bmc_segment_id,
  (id) => {
    if (!assignIpVisible.value) return
    if (!assignIpHydrating.value) assignIpForm.bmc_ip_id = null
    void loadAssignSegmentIpOptions('bmc', id, assignIpForm.bmc_ip_id)
  },
)
watch(
  () => assignIpForm.vip_segment_id,
  (id) => {
    if (!assignIpVisible.value) return
    if (!assignIpHydrating.value) assignIpForm.vip_ip_id = null
    void loadAssignSegmentIpOptions('vip', id, assignIpForm.vip_ip_id)
  },
)

async function openAssignIp(row: Device) {
  try {
    await ensureDeviceIpSegments()
    const detail = await getDevice(row.id)
    assignIpDevice.value = detail
    assignIpHydrating.value = true
    assignIpForm.system_segment_id = detail.system_segment_id || ''
    assignIpForm.system_ip_id = detail.system_ip_id || null
    assignIpForm.bmc_segment_id = detail.bmc_segment_id || ''
    assignIpForm.bmc_ip_id = detail.bmc_ip_id || null
    assignIpForm.vip_segment_id = detail.vip_segment_id || ''
    assignIpForm.vip_ip_id = detail.vip_ip_id || null
    assignIpVisible.value = true
    await Promise.all([
      assignIpForm.system_segment_id
        ? loadAssignSegmentIpOptions(
            'system',
            assignIpForm.system_segment_id,
            assignIpForm.system_ip_id,
          )
        : Promise.resolve((assignSystemIpOptions.value = [])),
      assignIpForm.bmc_segment_id
        ? loadAssignSegmentIpOptions('bmc', assignIpForm.bmc_segment_id, assignIpForm.bmc_ip_id)
        : Promise.resolve((assignBmcIpOptions.value = [])),
      assignIpForm.vip_segment_id
        ? loadAssignSegmentIpOptions('vip', assignIpForm.vip_segment_id, assignIpForm.vip_ip_id)
        : Promise.resolve((assignVipIpOptions.value = [])),
    ])
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '加载设备 IP 失败')
  } finally {
    assignIpHydrating.value = false
  }
}

async function handleAssignIpSubmit() {
  const row = assignIpDevice.value
  if (!row) return
  if (assignIpForm.vip_ip_id && !assignIpForm.system_ip_id && !assignIpForm.bmc_ip_id) {
    ElMessage.warning('分配虚拟IP前请先选择业务地址或带外地址')
    return
  }
  assignIpSaving.value = true
  try {
    await updateDevice(row.id, {
      system_ip_id: assignIpForm.system_ip_id || '',
      bmc_ip_id: assignIpForm.bmc_ip_id || '',
      vip_ip_id: assignIpForm.vip_ip_id || '',
    })
    ElMessage.success('IP 地址已分配')
    assignIpVisible.value = false
    await loadData()
    await refreshIpAfterDeviceChange()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '分配失败')
  } finally {
    assignIpSaving.value = false
  }
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
  const idx = models.value.findIndex((m) => m.id === created.id)
  if (idx >= 0) {
    models.value[idx] = created
    models.value = [...models.value]
    return
  }
  models.value = [...models.value, created].sort((a, b) => a.name.localeCompare(b.name))
}

function onManufacturerCreated(created: Manufacturer) {
  if (manufacturers.value.some((m) => m.id === created.id)) return
  manufacturers.value = [...manufacturers.value, created].sort((a, b) =>
    a.name.localeCompare(b.name),
  )
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
  if (profileSubTab.value === 'bmc') await deleteBmcProfile(row.id)
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
  openIpBatchCreate()
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
  if (!ipEditingId.value) return
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
    await updateIpAddress(ipEditingId.value, payload)
    ElMessage.success('已保存')
    ipDialogVisible.value = false
    await refreshIpDetail()
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
  await refreshIpDetail()
  await loadIpData()
}

function openIpBatchCreate() {
  ipBatchForm.application = ''
  ipBatchForm.network = ''
  ipBatchForm.prefix_len = 24
  ipBatchForm.gateway = ''
  ipBatchForm.reserved_ips = ''
  ipBatchForm.address_purpose = '业务地址'
  ipBatchForm.network_type = '互联网'
  ipBatchForm.location = ''
  ipBatchForm.remarks = ''
  ipBatchForm.dns = ''
  ipBatchForm.dns_secondary = ''
  ipBatchCreateVisible.value = true
  void loadLocationRefs().catch(() => undefined)
}

async function submitIpBatchCreate(ev?: Event) {
  ev?.preventDefault?.()
  if (!ipBatchForm.network.trim()) {
    ElMessage.warning('请填写 IP 地址段，如 172.17.0.0')
    return
  }
  if (!ipBatchForm.prefix_len || ipBatchForm.prefix_len < 8 || ipBatchForm.prefix_len > 30) {
    ElMessage.warning('请填写有效掩码位数（8–30）')
    return
  }
  ipBatchBusy.value = true
  try {
    const detail = await createIpSegment({
      application: ipBatchForm.application.trim() || null,
      network: ipBatchForm.network.trim(),
      prefix_len: Number(ipBatchForm.prefix_len),
      gateway: ipBatchForm.gateway.trim() || null,
      reserved_ips: ipBatchForm.reserved_ips.trim() || null,
      address_purpose: ipBatchForm.address_purpose || null,
      network_type: ipBatchForm.network_type || null,
      location: ipBatchForm.location.trim() || null,
      remarks: ipBatchForm.remarks.trim() || null,
      dns: ipBatchForm.dns.trim() || null,
      dns_secondary: ipBatchForm.dns_secondary.trim() || null,
    })
    ElMessage.success(
      `地址段已创建：已分配 ${detail.allocated_count} · 空闲 ${detail.free_count} · 保留 ${detail.reserved_count}`,
    )
    ipBatchCreateVisible.value = false
    await loadIpData()
    await openIpSegmentDetail(detail)
  } catch (error: unknown) {
    const err = error as {
      response?: {
        data?: {
          message?: string
          detail?: string
          details?: { detail?: string; errors?: Array<{ msg?: string }> }
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
        || err.response?.data?.details?.detail
        || err.response?.data?.message
        || err.response?.data?.detail
        || err.message
        || '创建地址段失败',
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
    if (ipDetailVisible.value) await refreshIpDetail()
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
    if (ipDetailVisible.value) await refreshIpDetail()
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
    if (ipDetailVisible.value) await refreshIpDetail()
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
    if (ipDetailVisible.value) await refreshIpDetail()
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
    if (ipDetailVisible.value) await refreshIpDetail()
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
    if (ipDetailVisible.value) await refreshIpDetail()
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
// 保留待恢复的参数档案/IP 表单逻辑，避免被生产构建误判为死代码。
void [
  paramDialogVisible, paramEditingId, DDR_OPTIONS, DISK_INTERFACE_OPTIONS, DISK_MEDIA_OPTIONS,
  resetParamForm, fillParamForm, buildParamPayload, addDiskRow, removeDiskRow,
  addOsTag, removeOsTag, addCustomRow, removeCustomRow, bindTypeLabel, resetIpForm,
]

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
                placeholder="搜索采购名称/编号/设备序号"
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
              <el-dropdown
                v-if="canUpdate || canDelete"
                trigger="click"
                :disabled="!selectedDevices.length"
                @command="handleBatchCommand"
              >
                <el-button :disabled="!selectedDevices.length" :loading="batchBusy">
                  批量修改
                  <span class="dropdown-caret">▾</span>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item v-if="canUpdate" command="contract">合同 / 合同设备</el-dropdown-item>
                    <el-dropdown-item v-if="canUpdate" command="type">类型</el-dropdown-item>
                    <el-dropdown-item v-if="canUpdate" command="model">型号</el-dropdown-item>
                    <el-dropdown-item v-if="canUpdate" command="manufacturer">产品厂商</el-dropdown-item>
                    <el-dropdown-item v-if="canUpdate" command="unmount">批量下架</el-dropdown-item>
                    <el-dropdown-item v-if="canUpdate" command="mount">移动设备</el-dropdown-item>
                    <el-dropdown-item v-if="canUpdate" command="ip">改 IP</el-dropdown-item>
                    <el-dropdown-item
                      v-if="canDelete"
                      command="delete"
                      divided
                      :disabled="batchBusy"
                    >
                      批量删除
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <span v-if="selectedDevices.length" class="batch-hint">已选 {{ selectedDevices.length }} 台</span>
            </div>
          </div>

          <el-table
            v-loading="loading"
            class="device-list-table"
            :data="tableData"
            stripe
            size="small"
            @selection-change="onSelectionChange"
          >
            <el-table-column
              type="selection"
              width="36"
              class-name="col-check"
              label-class-name="col-check"
            />
            <el-table-column
              type="index"
              label="序号"
              width="52"
              align="center"
              class-name="col-index"
              label-class-name="col-index"
              :index="(i: number) => (pagination.page - 1) * pagination.page_size + i + 1"
            />
            <el-table-column prop="hostname" label="设备编号" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.hostname || '—' }}</template>
            </el-table-column>
            <el-table-column prop="name" label="采购名称" min-width="130" show-overflow-tooltip>
              <template #default="{ row }">{{ row.name || '—' }}</template>
            </el-table-column>
            <el-table-column prop="device_model_name" label="产品型号" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.device_model_name || '—' }}</template>
            </el-table-column>
            <el-table-column prop="manufacturer_name" label="产品厂商" min-width="100" show-overflow-tooltip>
              <template #default="{ row }">{{ row.manufacturer_name || '—' }}</template>
            </el-table-column>
            <el-table-column label="上架位置" min-width="170" show-overflow-tooltip>
              <template #default="{ row }">{{ locationText(row) }}</template>
            </el-table-column>
            <el-table-column label="IP 地址" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">
                <div>{{ row.ip_summary || '—' }}</div>
                <div v-if="row.bmc_ip || row.vip" class="ip-extra">
                  <span v-if="row.bmc_ip">BMC: {{ row.bmc_ip }}</span>
                  <span v-if="row.vip">VIP: {{ row.vip }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="项目归属" min-width="110" show-overflow-tooltip>
              <template #default="{ row }">{{ row.project_scope || row.project_no || '—' }}</template>
            </el-table-column>
            <el-table-column label="项目应用" min-width="110" show-overflow-tooltip>
              <template #default="{ row }">{{ row.project_app || '—' }}</template>
            </el-table-column>
            <el-table-column prop="serial_number" label="设备序号" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.serial_number || '—' }}</template>
            </el-table-column>
            <el-table-column label="设备类型" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ deviceTypeDisplayName(row) }}</template>
            </el-table-column>
            <el-table-column label="类型归类" min-width="110" align="center">
              <template #default="{ row }">
                <span class="resource-class-badge sm" :data-class="deviceResourceClassOf(row)">
                  {{ deviceResourceClassLabel(row) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="88" align="center">
              <template #default="{ row }">{{ statusLabel[row.status] || row.status }}</template>
            </el-table-column>
            <el-table-column label="归属合同" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ row.contract_no || '—' }}</template>
            </el-table-column>
            <el-table-column label="设备高度" width="88" align="center">
              <template #default="{ row }">{{ row.height_u != null ? `${row.height_u}U` : '—' }}</template>
            </el-table-column>
            <el-table-column label="电源功率" width="96" align="center">
              <template #default="{ row }">{{ row.power != null ? `${row.power}W` : '—' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="88" fixed="right" align="center">
              <template #default="{ row }">
                <el-dropdown trigger="click">
                  <el-button type="primary" link>操作</el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item v-if="canUpdate" @click="openEdit(row)">编辑设备</el-dropdown-item>
                      <el-dropdown-item v-if="canUpdate" @click="openAssignIp(row)">分配IP地址</el-dropdown-item>
                      <el-dropdown-item v-if="canUpdate" @click="openStatusChange(row)">
                        修改设备状态
                      </el-dropdown-item>
                      <el-dropdown-item v-if="canUpdate" @click="openMount(row)">
                        移动设备位置
                      </el-dropdown-item>
                      <el-dropdown-item @click="viewDeviceParams(row)">查看设备参数</el-dropdown-item>
                      <el-dropdown-item v-if="row.rack_id" @click="openRackDetail(row)">
                        查看机柜位图
                      </el-dropdown-item>
                      <el-dropdown-item v-if="canDelete" divided @click="handleDelete(row)">
                        删除
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
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
            <el-tab-pane label="BMC 档案" name="bmc" />
            <el-tab-pane label="系统用户档案" name="system" />
            <el-tab-pane label="设备类型" name="type" />
            <el-tab-pane label="产品型号" name="model" />
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
            <el-table-column label="操作" width="88" align="center">
              <template #default="{ row }">
                <el-dropdown trigger="click">
                  <el-button type="primary" link>操作</el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item v-if="canUpdate" @click="openTypeEdit(row)">编辑</el-dropdown-item>
                      <el-dropdown-item
                        v-if="canUpdate && !row.is_system"
                        divided
                        @click="removeType(row)"
                      >
                        删除
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
          </el-table>
          <el-table v-else-if="profileSubTab === 'model'" :data="models" stripe>
            <el-table-column prop="code" label="编码" width="160" />
            <el-table-column prop="name" label="型号名称" min-width="160" />
            <el-table-column prop="manufacturer_name" label="产品厂商" width="120">
              <template #default="{ row }">{{ row.manufacturer_name || '—' }}</template>
            </el-table-column>
            <el-table-column prop="description" label="描述" min-width="180">
              <template #default="{ row }">{{ row.description || '—' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="88" align="center">
              <template #default="{ row }">
                <el-dropdown trigger="click">
                  <el-button type="primary" link>操作</el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item v-if="canUpdate" @click="openModelEdit(row)">编辑</el-dropdown-item>
                      <el-dropdown-item v-if="canUpdate" divided @click="removeModel(row)">删除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
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
            <el-table-column label="操作" width="88" align="center">
              <template #default="{ row }">
                <el-dropdown trigger="click">
                  <el-button type="primary" link>操作</el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item v-if="canUpdate" @click="openProfileEdit(row)">编辑</el-dropdown-item>
                      <el-dropdown-item v-if="canUpdate" divided @click="removeProfile(row)">删除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="IP 地址" name="ips">
          <div class="card-header">
            <div class="actions">
              <el-input
                v-model="ipKeyword"
                placeholder="搜索应用 / 地址段 / 网关 / 机房位置"
                clearable
                style="width: 260px"
                @keyup.enter="loadIpData"
              />
              <el-select
                v-model="ipAppTypeFilter"
                clearable
                filterable
                allow-create
                placeholder="地址用途"
                style="width: 140px"
                @change="loadIpData"
              >
                <el-option
                  v-for="o in IP_PURPOSE_OPTIONS"
                  :key="o.value"
                  :label="o.label"
                  :value="o.value"
                />
              </el-select>
              <el-button @click="loadIpData">搜索</el-button>
              <el-button v-if="canUpdate" type="primary" @click="openIpCreate">新建地址段</el-button>
            </div>
          </div>

          <el-table v-loading="ipLoading" :data="ipSegmentTable" stripe>
            <el-table-column type="index" label="序号" width="64" :index="(i: number) => (ipSegmentPagination.page - 1) * ipSegmentPagination.page_size + i + 1" />
            <el-table-column prop="application" label="应用" min-width="90">
              <template #default="{ row }">{{ row.application || '—' }}</template>
            </el-table-column>
            <el-table-column label="IP地址段" min-width="130">
              <template #default="{ row }">
                <el-button type="primary" link @click="openIpSegmentDetail(row)">
                  {{ row.network || row.start_ip }}
                </el-button>
              </template>
            </el-table-column>
            <el-table-column label="掩码" width="72" align="center">
              <template #default="{ row }">{{ row.prefix_len || row.netmask || '—' }}</template>
            </el-table-column>
            <el-table-column prop="gateway" label="网关" min-width="120">
              <template #default="{ row }">{{ row.gateway || '—' }}</template>
            </el-table-column>
            <el-table-column label="已分配个数" width="100" align="center" prop="allocated_count" />
            <el-table-column label="空闲可用" width="90" align="center">
              <template #default="{ row }">
                <span class="ip-free">{{ row.free_count }}</span>
              </template>
            </el-table-column>
            <el-table-column label="保留地址" width="90" align="center" prop="reserved_count" />
            <el-table-column label="地址用途" min-width="100">
              <template #default="{ row }">{{ row.address_purpose || '—' }}</template>
            </el-table-column>
            <el-table-column label="网络类型" width="100">
              <template #default="{ row }">{{ row.network_type || '—' }}</template>
            </el-table-column>
            <el-table-column label="所属机房位置" min-width="120">
              <template #default="{ row }">{{ row.location || '—' }}</template>
            </el-table-column>
            <el-table-column label="备注" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.remarks || '—' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="88" fixed="right" align="center">
              <template #default="{ row }">
                <el-dropdown trigger="click">
                  <el-button type="primary" link>操作</el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item @click="openIpSegmentDetail(row)">详情</el-dropdown-item>
                      <el-dropdown-item v-if="canUpdate" @click="openIpSegmentEdit(row)">编辑</el-dropdown-item>
                      <el-dropdown-item
                        v-if="canDelete"
                        divided
                        @click="handleIpSegmentDelete(row)"
                      >
                        删除
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
          </el-table>

          <div class="pager">
            <el-pagination
              v-model:current-page="ipSegmentPagination.page"
              v-model:page-size="ipSegmentPagination.page_size"
              :total="ipSegmentPagination.total"
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
      size="1080px"
      class="device-form-drawer"
    >
      <div class="device-form-sheet-wrap">
        <table class="device-form-sheet">
          <!-- 合同信息 -->
          <tr>
            <th rowspan="1" class="sheet-section">合同信息</th>
            <th>采购合同</th>
            <td>
              <el-select
                v-model="form.contract_id"
                clearable
                filterable
                placeholder="选择合同"
                @change="onFormContractChange"
              >
                <el-option
                  v-for="c in formContracts"
                  :key="c.id"
                  :label="c.project_no ? `${c.contract_no} · ${c.project_no}` : c.contract_no"
                  :value="c.id"
                />
              </el-select>
            </td>
            <th>合同设备</th>
            <td>
              <el-select
                v-model="form.contract_item_key"
                clearable
                filterable
                placeholder="读取合同"
                :disabled="!form.contract_id"
                @change="onFormContractItemChange"
              >
                <el-option
                  v-for="it in formContractItems"
                  :key="contractItemKey(it)"
                  :label="contractItemOptionLabel(it)"
                  :value="contractItemKey(it)"
                />
              </el-select>
            </td>
            <th>上架时间</th>
            <td>
              <el-date-picker
                v-model="form.mounted_at"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ss"
                placeholder="选择上架时间"
                style="width: 100%"
              />
            </td>
          </tr>

          <!-- 基本信息 -->
          <tr>
            <th rowspan="5" class="sheet-section">基本信息</th>
            <th>设备编号</th>
            <td>
              <el-input v-model="form.hostname" placeholder="唯一编号" />
            </td>
            <th>项目归属</th>
            <td>
              <el-input v-model="form.project_scope" placeholder="同步合同项目号或手工填写" />
            </td>
            <th>项目应用</th>
            <td>
              <el-input v-model="form.project_app" placeholder="业务应用/分区" />
            </td>
          </tr>
          <tr>
            <th>产品型号</th>
            <td>
              <div class="sheet-inline">
                <el-select
                  v-model="form.device_model_id"
                  filterable
                  allow-create
                  default-first-option
                  placeholder="同步合同 / 选择产品型号"
                  style="flex: 1"
                  @change="onDeviceModelSelect"
                >
                  <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.id" />
                </el-select>
                <el-button v-if="canCreate || canUpdate" link type="primary" @click="openModelCreate">新建</el-button>
              </div>
            </td>
            <th>产品厂商</th>
            <td>
              <el-select
                v-model="form.manufacturer_id"
                clearable
                filterable
                allow-create
                default-first-option
                placeholder="同步合同 / 产品厂商"
                @change="onManufacturerChange"
              >
                <el-option v-for="m in manufacturers" :key="m.id" :label="m.name" :value="m.id" />
              </el-select>
            </td>
            <th>设备类型</th>
            <td>
              <el-select
                :model-value="form.device_type_id || undefined"
                filterable
                placeholder="选择设备类型"
                @change="onDeviceTypePick"
              >
                <el-option
                  v-for="t in deviceTypeOptions"
                  :key="t.code"
                  :label="t.name"
                  :value="t.id || t.code"
                />
              </el-select>
            </td>
          </tr>
          <tr>
            <th>设备高度</th>
            <td>
              <div class="sheet-inline unit-row">
                <el-input-number v-model="form.height_u" :min="1" :max="10" controls-position="right" />
                <span class="unit-suffix">U</span>
              </div>
            </td>
            <th>电源功率</th>
            <td>
              <div class="sheet-inline unit-row">
                <el-input-number v-model="form.power" :min="0" :step="50" controls-position="right" />
                <span class="unit-suffix">W</span>
              </div>
            </td>
            <th>维保年限</th>
            <td>
              <div class="sheet-inline unit-row">
                <el-input-number
                  v-model="form.warranty_years"
                  :min="0"
                  :max="50"
                  controls-position="right"
                  placeholder="年"
                />
                <span class="unit-suffix">年</span>
              </div>
            </td>
          </tr>
          <tr>
            <th>设备序号</th>
            <td colspan="3">
              <el-input v-model="form.serial_number" placeholder="必填" />
            </td>
            <th>采购名称</th>
            <td>
              <el-input v-model="form.name" placeholder="与合同清单一致" />
            </td>
          </tr>
          <tr>
            <th>类型归类</th>
            <td colspan="5">
              <span class="resource-class-badge" :data-class="resourceClassKey">
                {{ resourceClassLabel }}
              </span>
              <span class="sheet-hint" style="display: inline; margin-left: 8px">由设备类型自动归类</span>
            </td>
          </tr>

          <!-- 上架信息 -->
          <tr>
            <th rowspan="4" class="sheet-section">上架信息</th>
            <th>中心机房</th>
            <td>
              <el-select
                v-model="form.room_id"
                clearable
                filterable
                placeholder="选择机房"
                @change="onFormRoomChange"
              >
                <el-option
                  v-for="r in rooms"
                  :key="r.id"
                  :label="r.datacenter_name ? `${r.datacenter_name} · ${r.name}` : r.name"
                  :value="r.id"
                />
              </el-select>
              <div v-if="formDatacenterLabel" class="sheet-hint">数据中心：{{ formDatacenterLabel }}</div>
            </td>
            <th>机柜位置</th>
            <td>
              <el-select
                v-model="form.rack_id"
                clearable
                filterable
                placeholder="选择机柜"
                :disabled="!form.room_id"
                @change="(id: string) => loadFormRackLayout(id || '')"
              >
                <el-option
                  v-for="r in formRacks"
                  :key="r.id"
                  :label="`${r.code} · 空闲 ${r.free_u}U`"
                  :value="r.id"
                />
              </el-select>
            </td>
            <th>机柜U位</th>
            <td>
              <el-input-number
                v-model="form.u_position"
                :min="1"
                :max="formRackMeta?.total_u || 60"
                :disabled="!form.rack_id"
                controls-position="right"
              />
            </td>
          </tr>
          <tr>
            <th>业务IP地址</th>
            <td colspan="5">
              <div class="sheet-ip-row">
                <el-select
                  v-model="form.system_segment_id"
                  clearable
                  filterable
                  placeholder="选择地址段"
                  style="width: 220px"
                >
                  <el-option
                    v-for="s in deviceIpSegments"
                    :key="s.id"
                    :label="`${s.application ? s.application + ' · ' : ''}${s.network}/${s.prefix_len}`"
                    :value="s.id"
                  />
                </el-select>
                <el-select
                  v-model="form.system_ip_id"
                  clearable
                  filterable
                  :loading="ipOptionsLoading.system"
                  :disabled="!form.system_segment_id"
                  placeholder="选择可用IP"
                  style="width: 200px"
                >
                  <el-option
                    v-for="ip in systemIpOptions"
                    :key="ip.id"
                    :label="ip.system_ip"
                    :value="ip.id"
                  />
                </el-select>
                <el-select
                  v-model="form.system_profile_id"
                  clearable
                  filterable
                  placeholder="系统用户档案关联"
                  style="flex: 1"
                >
                  <el-option
                    v-for="p in systemProfiles"
                    :key="p.id"
                    :label="p.summary ? `${p.name} · ${p.summary}` : p.name"
                    :value="p.id"
                  />
                </el-select>
              </div>
            </td>
          </tr>
          <tr>
            <th>带外IP地址</th>
            <td colspan="5">
              <div class="sheet-ip-row">
                <el-select
                  v-model="form.bmc_segment_id"
                  clearable
                  filterable
                  placeholder="选择地址段"
                  style="width: 220px"
                >
                  <el-option
                    v-for="s in deviceIpSegments"
                    :key="s.id"
                    :label="`${s.application ? s.application + ' · ' : ''}${s.network}/${s.prefix_len}`"
                    :value="s.id"
                  />
                </el-select>
                <el-select
                  v-model="form.bmc_ip_id"
                  clearable
                  filterable
                  :loading="ipOptionsLoading.bmc"
                  :disabled="!form.bmc_segment_id"
                  placeholder="选择可用IP"
                  style="width: 200px"
                >
                  <el-option
                    v-for="ip in bmcIpOptions"
                    :key="ip.id"
                    :label="ip.system_ip"
                    :value="ip.id"
                  />
                </el-select>
                <el-select
                  v-model="form.bmc_profile_id"
                  clearable
                  filterable
                  placeholder="BMC档案关联"
                  style="flex: 1"
                >
                  <el-option
                    v-for="p in bmcProfiles"
                    :key="p.id"
                    :label="p.summary ? `${p.name} · ${p.summary}` : p.name"
                    :value="p.id"
                  />
                </el-select>
              </div>
            </td>
          </tr>
          <tr>
            <th>虚拟IP</th>
            <td colspan="3">
              <div class="sheet-ip-row">
                <el-select
                  v-model="form.vip_segment_id"
                  clearable
                  filterable
                  placeholder="选择地址段"
                  style="width: 220px"
                >
                  <el-option
                    v-for="s in deviceIpSegments"
                    :key="s.id"
                    :label="`${s.application ? s.application + ' · ' : ''}${s.network}/${s.prefix_len}`"
                    :value="s.id"
                  />
                </el-select>
                <el-select
                  v-model="form.vip_ip_id"
                  clearable
                  filterable
                  :loading="ipOptionsLoading.vip"
                  :disabled="!form.vip_segment_id"
                  placeholder="虚拟IP（可共用）"
                  style="width: 200px"
                >
                  <el-option
                    v-for="ip in vipIpOptions"
                    :key="ip.id"
                    :label="ip.system_ip"
                    :value="ip.id"
                  />
                </el-select>
              </div>
            </td>
            <th>设备参数</th>
            <td>
              <el-select
                v-model="form.param_profile_id"
                clearable
                filterable
                placeholder="可选"
              >
                <el-option
                  v-for="(p, idx) in paramProfiles"
                  :key="p.id"
                  :label="`${idx + 1}.${p.name}：${p.code}`"
                  :value="p.id"
                />
              </el-select>
            </td>
          </tr>
        </table>

        <div class="sheet-desc-row">
          <span class="sheet-desc-label">描述</span>
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="备注（可选）" />
        </div>

        <template v-if="editingId && editingPanel?.port_layout">
          <div class="sheet-panel-block">
            <div class="sheet-panel-title">设备定义面板</div>
            <DevicePanelPreview
              :port-layout="editingPanel.port_layout"
              :network-kind="editingPanel.network_kind"
              :device-name="editingPanel.device_name"
            />
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存</el-button>
      </template>
    </el-drawer>

    <el-dialog
      v-model="paramViewVisible"
      title="查看设备参数"
      width="780px"
      destroy-on-close
      top="6vh"
      class="param-view-dialog"
    >
      <div v-loading="paramViewLoading" class="param-view-body">
        <div v-if="paramViewDevice" class="param-view-device">
          设备：
          <strong>{{ paramViewDevice.name || paramViewDevice.hostname || '—' }}</strong>
          <span v-if="paramViewDevice.hostname" class="muted">
            （编号 {{ paramViewDevice.hostname }}）
          </span>
        </div>
        <template v-if="paramViewProfile">
          <table class="param-view-sheet">
            <tr>
              <th>设备名称</th>
              <td>{{ paramViewProfile.name || '—' }}</td>
              <th>设备参数ID</th>
              <td>{{ paramViewProfile.code || '—' }}</td>
            </tr>
            <tr>
              <th>产品型号</th>
              <td>
                {{
                  paramViewProfile.source_device_model
                    || paramViewProfile.payload?.source_device_model
                    || '—'
                }}
              </td>
              <th>产品厂商</th>
              <td>
                {{
                  paramViewProfile.source_manufacturer
                    || paramViewProfile.payload?.source_manufacturer
                    || '—'
                }}
              </td>
            </tr>
            <tr>
              <th>设备类型</th>
              <td>{{ paramViewTypeName(paramViewProfile) }}</td>
              <th>类型归类</th>
              <td>{{ paramViewTypeClass(paramViewProfile) }}</td>
            </tr>
            <tr>
              <th>状态</th>
              <td>
                <el-tag
                  :type="paramViewProfile.is_complete ? 'success' : 'danger'"
                  size="small"
                  effect="plain"
                >
                  {{ paramViewProfile.is_complete ? '已完善' : '待完善' }}
                </el-tag>
              </td>
              <th></th>
              <td></td>
            </tr>
            <tr>
              <th>配置摘要</th>
              <td colspan="3">{{ paramViewProfile.summary || '—' }}</td>
            </tr>
            <tr v-if="paramViewProfile.missing_fields?.length">
              <th>缺失字段</th>
              <td colspan="3" class="warn-text">{{ paramViewProfile.missing_fields.join('、') }}</td>
            </tr>
            <tr>
              <th>系统盘</th>
              <td colspan="3">
                <template v-if="paramViewDisks('system').length">
                  <div v-for="(d, i) in paramViewDisks('system')" :key="`sys-${i}`">
                    {{ formatDiskSpec(d) }}
                  </div>
                </template>
                <template v-else>—</template>
              </td>
            </tr>
            <tr>
              <th>数据盘</th>
              <td colspan="3">
                <template v-if="paramViewDisks('data').length">
                  <div v-for="(d, i) in paramViewDisks('data')" :key="`data-${i}`">
                    规格 {{ i + 1 }}：{{ formatDiskSpec(d) }}
                  </div>
                </template>
                <template v-else>—</template>
              </td>
            </tr>
            <tr>
              <th>详细参数</th>
              <td colspan="3" class="pre-wrap">
                {{
                  paramViewProfile.detail_params
                    || paramViewProfile.payload?.detail_params
                    || '—'
                }}
              </td>
            </tr>
            <tr>
              <th>其他参数</th>
              <td colspan="3" class="pre-wrap">{{ paramViewOtherText(paramViewProfile) || '—' }}</td>
            </tr>
            <tr v-if="paramViewProfile.description">
              <th>描述</th>
              <td colspan="3" class="pre-wrap">{{ paramViewProfile.description }}</td>
            </tr>
          </table>
        </template>
        <el-empty v-else-if="!paramViewLoading" description="暂无合同设备参数" />
      </div>
      <template #footer>
        <el-button type="primary" @click="paramViewVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="mountVisible" :title="mountDialogTitle" width="880px" destroy-on-close>
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
            :visual-style="(mountRackMeta?.visual_style as any) || 'classic'"
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

    <el-dialog
      v-model="statusChangeVisible"
      title="修改设备状态"
      width="480px"
      destroy-on-close
    >
      <p class="status-change-current">
        当前设备：
        <strong>{{ statusChangeDevice?.name || statusChangeDevice?.hostname || '—' }}</strong>
        · 状态 {{ statusLabel[statusChangeDevice?.status || ''] || statusChangeDevice?.status || '—' }}
      </p>
      <el-radio-group v-model="statusChangeTarget" class="status-change-options">
        <el-radio
          v-for="opt in DEVICE_STATUS_OPTIONS"
          :key="opt.value"
          :value="opt.value"
          class="status-change-option"
        >
          <span class="status-change-label">{{ opt.label }}</span>
          <span class="status-change-hint">{{ opt.hint }}</span>
        </el-radio>
      </el-radio-group>
      <template #footer>
        <el-button @click="statusChangeVisible = false">取消</el-button>
        <el-button type="primary" :loading="statusChangeSaving" @click="handleStatusChangeConfirm">
          确定
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="assignIpVisible"
      title="分配IP地址"
      width="640px"
      destroy-on-close
    >
      <p class="status-change-current">
        设备：
        <strong>{{ assignIpDevice?.name || assignIpDevice?.hostname || '—' }}</strong>
        · 从已创建地址段中手动选择业务 / BMC / VIP
      </p>
      <el-form label-width="96px">
        <el-form-item label="业务地址">
          <div class="ip-assign-row">
            <el-select
              v-model="assignIpForm.system_segment_id"
              clearable
              filterable
              placeholder="选择地址段"
              style="width: 48%"
            >
              <el-option
                v-for="s in deviceIpSegments"
                :key="s.id"
                :label="`${s.application ? s.application + ' · ' : ''}${s.network}/${s.prefix_len}`"
                :value="s.id"
              />
            </el-select>
            <el-select
              v-model="assignIpForm.system_ip_id"
              clearable
              filterable
              :loading="assignIpLoading.system"
              :disabled="!assignIpForm.system_segment_id"
              placeholder="选择可用业务IP"
              style="width: 48%"
            >
              <el-option
                v-for="ip in assignSystemIpOptions"
                :key="ip.id"
                :label="ip.system_ip"
                :value="ip.id"
              />
            </el-select>
          </div>
          <p class="bind-device-hint">仅显示空闲地址；清空表示取消分配</p>
        </el-form-item>
        <el-form-item label="带外地址">
          <div class="ip-assign-row">
            <el-select
              v-model="assignIpForm.bmc_segment_id"
              clearable
              filterable
              placeholder="选择地址段"
              style="width: 48%"
            >
              <el-option
                v-for="s in deviceIpSegments"
                :key="s.id"
                :label="`${s.application ? s.application + ' · ' : ''}${s.network}/${s.prefix_len}`"
                :value="s.id"
              />
            </el-select>
            <el-select
              v-model="assignIpForm.bmc_ip_id"
              clearable
              filterable
              :loading="assignIpLoading.bmc"
              :disabled="!assignIpForm.bmc_segment_id"
              placeholder="选择可用BMC IP"
              style="width: 48%"
            >
              <el-option
                v-for="ip in assignBmcIpOptions"
                :key="ip.id"
                :label="ip.system_ip"
                :value="ip.id"
              />
            </el-select>
          </div>
          <p class="bind-device-hint">仅显示空闲地址，不可与其他设备重复使用</p>
        </el-form-item>
        <el-form-item label="虚拟IP">
          <div class="ip-assign-row">
            <el-select
              v-model="assignIpForm.vip_segment_id"
              clearable
              filterable
              placeholder="选择地址段"
              style="width: 48%"
            >
              <el-option
                v-for="s in deviceIpSegments"
                :key="s.id"
                :label="`${s.application ? s.application + ' · ' : ''}${s.network}/${s.prefix_len}`"
                :value="s.id"
              />
            </el-select>
            <el-select
              v-model="assignIpForm.vip_ip_id"
              clearable
              filterable
              :loading="assignIpLoading.vip"
              :disabled="!assignIpForm.vip_segment_id"
              placeholder="选择虚拟IP（可共用）"
              style="width: 48%"
            >
              <el-option
                v-for="ip in assignVipIpOptions"
                :key="ip.id"
                :label="ip.system_ip"
                :value="ip.id"
              />
            </el-select>
          </div>
          <p class="bind-device-hint">虚拟IP可被多台设备共用；需先分配业务或带外地址</p>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignIpVisible = false">取消</el-button>
        <el-button type="primary" :loading="assignIpSaving" @click="handleAssignIpSubmit">
          确认分配
        </el-button>
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
          :visual-style="(rackDetailRack.visual_style as any) || 'classic'"
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
      :manufacturers="manufacturers"
      :contracts="contracts"
      @success="onBatchCreateSuccess"
      @type-created="onTypeCreated"
      @model-created="onModelCreated"
      @manufacturer-created="onManufacturerCreated"
    />

    <BatchEditDeviceDialog
      v-model="batchEditVisible"
      :mode="batchEditMode"
      :devices="selectedDevices"
      :rooms="rooms"
      :racks="racks"
      :models="models"
      :types="types"
      :manufacturers="manufacturers"
      :contracts="contracts"
      @success="onBatchEditSuccess"
      @model-created="onModelCreated"
      @manufacturer-created="onManufacturerCreated"
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
      :title="modelEditingId ? '编辑产品型号' : '新建自定义产品型号'"
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

    <el-dialog
      v-model="ipDialogVisible"
      title="编辑 IP 地址"
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
      title="新建地址段"
      width="600px"
      destroy-on-close
      @closed="ipBatchBusy = false"
    >
      <el-form label-width="120px" @submit.prevent="submitIpBatchCreate">
        <el-form-item label="应用">
          <el-input v-model="ipBatchForm.application" placeholder="如 B" />
        </el-form-item>
        <el-form-item label="IP地址段" required>
          <el-input v-model="ipBatchForm.network" placeholder="如 172.17.0.0" />
        </el-form-item>
        <el-form-item label="掩码" required>
          <el-input-number v-model="ipBatchForm.prefix_len" :min="8" :max="30" controls-position="right" />
          <span class="field-hint-inline">位数，例如 24 表示 /24</span>
        </el-form-item>
        <el-form-item label="网关">
          <el-input v-model="ipBatchForm.gateway" placeholder="如 172.17.0.1" />
        </el-form-item>
        <el-form-item label="保留地址">
          <el-input
            v-model="ipBatchForm.reserved_ips"
            type="textarea"
            :rows="2"
            placeholder="可选。填写具体保留 IP，多个用逗号/空格/换行分隔，也支持范围如 172.17.0.10-172.17.0.12"
          />
        </el-form-item>
        <el-form-item label="地址用途">
          <el-select
            v-model="ipBatchForm.address_purpose"
            clearable
            filterable
            allow-create
            default-first-option
            placeholder="选择预设，或输入自定义用途后回车"
            style="width: 100%"
          >
            <el-option v-for="o in IP_PURPOSE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="网络类型">
          <el-select
            v-model="ipBatchForm.network_type"
            clearable
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入自定义网络类型"
            style="width: 100%"
          >
            <el-option v-for="o in IP_NETWORK_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属机房位置">
          <el-select
            v-model="ipBatchForm.location"
            clearable
            filterable
            allow-create
            default-first-option
            placeholder="选择已建机房，或输入自定义位置后回车"
            style="width: 100%"
          >
            <el-option
              v-for="r in rooms"
              :key="r.id"
              :label="roomLocationLabel(r)"
              :value="roomLocationLabel(r)"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="ipBatchForm.remarks" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ipBatchCreateVisible = false">取消</el-button>
        <el-button type="primary" :loading="ipBatchBusy" @click="submitIpBatchCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="ipDetailVisible"
      :title="ipDetail ? `地址段详情 · ${ipDetail.name}` : '地址段详情'"
      size="860px"
      destroy-on-close
    >
      <div v-loading="ipDetailLoading" class="ip-segment-detail">
        <template v-if="ipDetail">
          <div class="ip-segment-meta">
            <div class="meta-item"><label>应用</label><span>{{ ipDetail.application || '—' }}</span></div>
            <div class="meta-item"><label>IP地址段</label><span>{{ ipDetail.network }}/{{ ipDetail.prefix_len }}</span></div>
            <div class="meta-item"><label>网关</label><span>{{ ipDetail.gateway || '—' }}</span></div>
            <div class="meta-item"><label>已分配</label><span>{{ ipDetail.allocated_count }}</span></div>
            <div class="meta-item"><label>空闲可用</label><span class="ip-free">{{ ipDetail.free_count }}</span></div>
            <div class="meta-item"><label>保留地址</label><span>{{ ipDetail.reserved_count }}</span></div>
            <div class="meta-item"><label>地址用途</label><span>{{ ipDetail.address_purpose || '—' }}</span></div>
            <div class="meta-item"><label>网络类型</label><span>{{ ipDetail.network_type || '—' }}</span></div>
            <div class="meta-item"><label>所属机房位置</label><span>{{ ipDetail.location || '—' }}</span></div>
            <div class="meta-item"><label>备注</label><span>{{ ipDetail.remarks || '—' }}</span></div>
          </div>
          <div class="actions" style="margin-bottom: 12px">
            <el-button v-if="canUpdate" @click="openIpSegmentEdit">编辑段信息</el-button>
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
            <el-button
              v-if="canDelete"
              type="danger"
              :disabled="!selectedIps.length"
              :loading="ipBatchBusy"
              @click="handleIpBatchDelete"
            >
              批量删除
            </el-button>
            <span v-if="selectedIps.length" class="batch-hint">已选 {{ selectedIps.length }} 条</span>
          </div>
          <el-table
            v-loading="ipDetailAddressesLoading"
            :data="ipDetail.addresses"
            stripe
            max-height="560"
            @selection-change="onIpSelectionChange"
          >
            <el-table-column type="selection" width="48" />
            <el-table-column prop="system_ip" label="系统 IP" min-width="120" />
            <el-table-column prop="bmc_ip" label="BMC IP" min-width="120">
              <template #default="{ row }">
                <span :class="{ 'text-muted': !row.bmc_ip }">{{ row.bmc_ip || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="ipStatusMeta(row.status).type" size="small">
                  {{ ipStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="分配设备" min-width="140">
              <template #default="{ row }">
                <span :class="{ 'text-muted': !row.device_name }">{{ row.device_name || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="关联位置" min-width="160">
              <template #default="{ row }">{{ formatBindLocation(row) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="88" fixed="right" align="center">
              <template #default="{ row }">
                <el-dropdown trigger="click">
                  <el-button type="primary" link>操作</el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item v-if="canUpdate" @click="openIpEdit(row)">编辑</el-dropdown-item>
                      <el-dropdown-item v-if="canUpdate" @click="openIpBindSingle(row)">关联</el-dropdown-item>
                      <el-dropdown-item
                        v-if="canUpdate && row.bind_type !== 'none'"
                        @click="handleIpRelease(row)"
                      >
                        释放
                      </el-dropdown-item>
                      <el-dropdown-item v-if="canUpdate" @click="handleIpToggleDisabled(row)">
                        {{ row.status === 'disabled' ? '启用' : '禁用' }}
                      </el-dropdown-item>
                      <el-dropdown-item v-if="canDelete" divided @click="handleIpDelete(row)">
                        删除
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </div>
    </el-drawer>

    <el-dialog v-model="ipSegmentEditVisible" title="编辑地址段信息" width="520px">
      <el-form label-width="120px">
        <el-form-item label="应用">
          <el-input v-model="ipSegmentEditForm.application" />
        </el-form-item>
        <el-form-item label="网关">
          <el-input v-model="ipSegmentEditForm.gateway" />
        </el-form-item>
        <el-form-item label="地址用途">
          <el-select
            v-model="ipSegmentEditForm.address_purpose"
            clearable
            filterable
            allow-create
            default-first-option
            placeholder="选择预设，或输入自定义用途后回车"
            style="width: 100%"
          >
            <el-option v-for="o in IP_PURPOSE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="网络类型">
          <el-select
            v-model="ipSegmentEditForm.network_type"
            clearable
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入自定义网络类型"
            style="width: 100%"
          >
            <el-option v-for="o in IP_NETWORK_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属机房位置">
          <el-select
            v-model="ipSegmentEditForm.location"
            clearable
            filterable
            allow-create
            default-first-option
            placeholder="选择已建机房，或输入自定义位置后回车"
            style="width: 100%"
          >
            <el-option
              v-for="r in rooms"
              :key="r.id"
              :label="roomLocationLabel(r)"
              :value="roomLocationLabel(r)"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="ipSegmentEditForm.remarks" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ipSegmentEditVisible = false">取消</el-button>
        <el-button type="primary" @click="saveIpSegmentEdit">保存</el-button>
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

.status-change-current {
  margin: 0 0 14px;
  color: #607080;
  font-size: 13px;
}

.status-change-options {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
  width: 100%;
}

.status-change-option {
  display: flex;
  align-items: center;
  height: auto;
  margin: 0;
  padding: 8px 10px;
  border: 1px solid #e4ebf2;
  border-radius: 8px;
}

.status-change-label {
  font-weight: 600;
  margin-right: 8px;
}

.status-change-hint {
  color: #8a9bab;
  font-size: 12px;
}

.ip-assign-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
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
/* 多选框与序号紧挨，压缩列间距 */
.device-list-table :deep(th.col-check),
.device-list-table :deep(td.col-check) {
  padding-left: 8px !important;
  padding-right: 0 !important;
}
.device-list-table :deep(th.col-index),
.device-list-table :deep(td.col-index) {
  padding-left: 0 !important;
  padding-right: 6px !important;
}
.device-list-table :deep(.col-check .cell),
.device-list-table :deep(.col-index .cell) {
  padding-left: 0;
  padding-right: 0;
}
.device-list-table :deep(.el-table-column--selection .cell) {
  display: flex;
  justify-content: center;
  padding: 0;
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
.ip-free {
  color: var(--el-color-success);
  font-weight: 600;
}
.field-hint-inline {
  margin-left: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.ip-segment-detail {
  min-height: 240px;
}
.ip-segment-meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px 16px;
  margin-bottom: 16px;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
}
.ip-segment-meta .meta-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.ip-segment-meta label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.ip-segment-meta span {
  font-size: 13px;
  color: var(--el-text-color-primary);
  word-break: break-all;
}
.ip-extra {
  margin-top: 2px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* —— 新建设备 / 编辑设备：表格表单 —— */
.device-form-sheet-wrap {
  padding: 4px 2px 12px;
  background: linear-gradient(180deg, #d6e6f5 0%, #e8f0f8 40%, #eef3f8 100%);
  border-radius: 4px;
}
.device-form-sheet {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  background: #c5d8ec;
}
.device-form-sheet th,
.device-form-sheet td {
  border: 1px solid #5a6b7c;
  padding: 6px 8px;
  vertical-align: middle;
  font-size: 13px;
}
.device-form-sheet th {
  background: #a8c0d8;
  color: #1f2933;
  font-weight: 600;
  text-align: center;
  white-space: nowrap;
  width: 96px;
}
.device-form-sheet td {
  background: #e7eef6;
}
.device-form-sheet .sheet-section {
  width: 52px;
  writing-mode: vertical-rl;
  text-orientation: mixed;
  letter-spacing: 0.2em;
  background: #7fa3c4;
  color: #0f1720;
  font-size: 14px;
  font-weight: 700;
}
.device-form-sheet :deep(.el-select),
.device-form-sheet :deep(.el-input),
.device-form-sheet :deep(.el-input-number),
.device-form-sheet :deep(.el-date-editor) {
  width: 100%;
}
.device-form-sheet :deep(.el-input__wrapper),
.device-form-sheet :deep(.el-select__wrapper),
.device-form-sheet :deep(.el-textarea__inner) {
  border-radius: 2px;
  background: #f7fafc;
  box-shadow: 0 0 0 1px #7a8a9a inset;
}
.sheet-inline {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}
.sheet-inline.unit-row :deep(.el-input-number) {
  flex: 1;
}
.unit-suffix {
  flex-shrink: 0;
  color: #334155;
  font-weight: 600;
}
.sheet-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #475569;
  line-height: 1.4;
}
.sheet-ip-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  width: 100%;
}
.mount-type-radios {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.mount-type-radios :deep(.el-radio) {
  margin-right: 0;
  background: #f8fafc;
}
.resource-class-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  border: 1px solid transparent;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.55) inset;
}
.resource-class-badge.sm {
  padding: 2px 8px;
  font-size: 12px;
  letter-spacing: 0.02em;
}
.param-view-body {
  min-height: 120px;
}
.param-view-device {
  margin-bottom: 12px;
  font-size: 13px;
  color: #334155;
}
.param-view-device .muted {
  color: #64748b;
  margin-left: 4px;
}
.param-view-sheet {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 13px;
}
.param-view-sheet th,
.param-view-sheet td {
  border: 1px solid #5a6b7c;
  padding: 8px 10px;
  vertical-align: top;
  word-break: break-word;
}
.param-view-sheet th {
  width: 96px;
  background: #a8c0d8;
  color: #1f2933;
  font-weight: 600;
  text-align: center;
  white-space: nowrap;
}
.param-view-sheet td {
  background: #e7eef6;
}
.param-view-sheet .pre-wrap {
  white-space: pre-wrap;
}
.param-view-sheet .warn-text {
  color: #b91c1c;
}
.resource-class-badge[data-class='compute'] {
  color: #0b3d2e;
  background: linear-gradient(135deg, #6ee7b7, #34d399);
  border-color: #059669;
}
.resource-class-badge[data-class='network'] {
  color: #0c2d6b;
  background: linear-gradient(135deg, #93c5fd, #3b82f6);
  border-color: #1d4ed8;
}
.resource-class-badge[data-class='storage'] {
  color: #4a1d04;
  background: linear-gradient(135deg, #fdba74, #f97316);
  border-color: #c2410c;
}
.resource-class-badge[data-class='ai'] {
  color: #083344;
  background: linear-gradient(135deg, #67e8f9, #06b6d4);
  border-color: #0e7490;
}
.resource-class-badge[data-class='security'] {
  color: #7f1d1d;
  background: linear-gradient(135deg, #fca5a5, #ef4444);
  border-color: #b91c1c;
}
.resource-class-badge[data-class='other'] {
  color: #1e293b;
  background: linear-gradient(135deg, #cbd5e1, #94a3b8);
  border-color: #475569;
}
.sheet-desc-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin-top: 10px;
  padding: 8px 10px;
  border: 1px solid #5a6b7c;
  background: #e7eef6;
}
.sheet-desc-label {
  flex-shrink: 0;
  width: 52px;
  padding-top: 6px;
  font-weight: 600;
  color: #1f2933;
  text-align: center;
}
.sheet-panel-block {
  margin-top: 12px;
  padding: 10px;
  border: 1px solid #5a6b7c;
  background: #e7eef6;
}
.sheet-panel-title {
  margin-bottom: 8px;
  font-weight: 700;
  color: #1f2933;
}
</style>
