<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createDeviceType,
  createParamProfile,
  deleteParamProfile,
  downloadParamProfilesTemplate,
  exportParamProfiles,
  importParamProfiles,
  listDeviceTypes,
  listParamProfiles,
  syncParamProfilesFromContracts,
  updateDeviceType,
  updateParamProfile,
  type DeviceType,
  type DiskRole,
  type ParamDiskSpec,
  type ParamProfile,
  type ParamProfilePayload,
} from '@/api/device'
import { getContractSummary } from '@/api/contract'
import { useAuthStore } from '@/stores/auth'
import ParamProfileDetailDialog from '@/components/ParamProfileDetailDialog.vue'
import {
  DEVICE_TYPE_CODES,
  DEVICE_TYPE_FALLBACK_NAMES,
  RESOURCE_CLASS_LABELS,
  buildDeviceTypeOptions,
  displayDeviceTypeName,
  resolveDeviceTypeCode,
  resourceClassOf,
  type DeviceTypeCode,
} from '@/utils/deviceTypeCatalog'

const auth = useAuthStore()
const route = useRoute()
const canUpdate = auth.hasPermission('device:update')
const canCreate = auth.hasPermission('device:create')
const canDelete = auth.hasPermission('device:delete') || canUpdate

const loading = ref(false)
const syncing = ref(false)
const exporting = ref(false)
const importing = ref(false)
const saving = ref(false)
const profiles = ref<ParamProfile[]>([])
const deviceTypes = ref<DeviceType[]>([])
/** 采购汇总设备名称（小写）集合，用于展示关联状态 */
const summaryNameKeys = ref<Set<string>>(new Set())
const dialogVisible = ref(false)
const editingId = ref<string | null>(null)
const editingPayload = ref<ParamProfilePayload | null>(null)
const importInput = ref<HTMLInputElement | null>(null)
const detailVisible = ref(false)
const detailProfile = ref<ParamProfile | null>(null)

/** 与设备管理同一组设备类型（标准名称 + 下拉样式） */
const deviceTypeOptions = computed(() => buildDeviceTypeOptions(deviceTypes.value))

const filters = reactive({
  keyword: '',
  status: 'all' as 'all' | 'incomplete' | 'complete',
  manufacturer: '',
  device_type_id: '',
})

const DISK_INTERFACE_OPTIONS = ['SATA', 'SAS', 'NVMe', 'PCIe', 'M.2', 'U.2']
const INTERFACE_CARD_TYPE_OPTIONS = ['400G', '100G', '40G', '25G', '10G', '1G']
const UPLINK_PORT_TYPE_OPTIONS = ['400G', '100G', '40G', '25G', '10G']
const DISK_MEDIA_OPTIONS = [
  { value: 'ssd', label: 'SSD' },
  { value: 'hdd', label: 'HDD' },
  { value: 'nvme', label: 'NVMe' },
]
const MEMORY_TYPE_OPTIONS = ['DDR4', 'DDR5', 'DDR4/5', 'LPDDR5']
const ONBOARD_TYPE_OPTIONS = ['RJ45', 'SFP', 'SFP+', 'QSFP28', '光口', '电口']
const MAX_DISK_SPEC_COUNT = 20

function emptyDisk(role: DiskRole): ParamDiskSpec {
  return { size_gb: null, count: null, interface: null, media_type: null, role }
}

const form = reactive({
  code: '',
  name: '',
  description: '',
  device_type_id: '' as string,
  source_device_model: '',
  source_manufacturer: '',
  cpu_model: '',
  cpu_count: null as number | null,
  cpu_cores: null as number | null,
  memory_ddr: '',
  memory_stick_gb: null as number | null,
  memory_total_gb: null as number | null,
  systemDisk: emptyDisk('system'),
  cacheDisk: emptyDisk('cache'),
  dataDisks: [emptyDisk('data'), emptyDisk('data')] as ParamDiskSpec[],
  ge_nic_count: null as number | null,
  ge_port_count: null as number | null,
  xe_nic_count: null as number | null,
  xe_port_count: null as number | null,
  onboard_type: '',
  onboard_count: null as number | null,
  pcie_slot_count: null as number | null,
  raid_model: '',
  gpu_model: '',
  gpu_count: null as number | null,
  gpu_vram_gb: null as number | null,
  gpu_bandwidth: '',
  switching_capacity: '',
  forwarding_rate: '',
  service_card_count: null as number | null,
  fabric_card_count: null as number | null,
  interface_card_count: null as number | null,
  interface_card_type: '' as string,
  downlink_port_count: null as number | null,
  uplink_port_type: '' as string,
  uplink_port_count: null as number | null,
  psu_power_w: null as number | null,
  height_u: null as number | null,
  other_params: '',
})

function isDiskRowFilled(d: ParamDiskSpec): boolean {
  return d.size_gb != null || d.count != null || !!d.interface || !!d.media_type
}

function deviceTypeName(typeId: string | null | undefined) {
  return displayDeviceTypeName(deviceTypes.value, typeId)
}

function typeClassOf(row: ParamProfile) {
  const typeId = typeIdOf(row)
  const code = resolveDeviceTypeCode(deviceTypes.value, typeId)
  return RESOURCE_CLASS_LABELS[resourceClassOf(code)]
}

function modelOf(row: ParamProfile) {
  return row.source_device_model || row.payload?.source_device_model || ''
}

function formatDiskBrief(d: ParamDiskSpec) {
  const bits: string[] = []
  if (d.count != null && d.size_gb != null) bits.push(`${d.count}×${d.size_gb}GB`)
  else if (d.size_gb != null) bits.push(`${d.size_gb}GB`)
  else if (d.count != null) bits.push(`${d.count}块`)
  if (d.interface) bits.push(d.interface)
  if (d.media_type) bits.push(String(d.media_type).toUpperCase())
  return bits.join(' ')
}

/** 配置参数：将全部明细合并到一个单元格文案 */
function configParamsOf(row: ParamProfile) {
  const p = row.payload || {}
  const parts: string[] = []
  if (p.psu_power_w != null) parts.push(`电源 ${Number(p.psu_power_w)}W`)
  if (p.height_u != null) parts.push(`高度 ${p.height_u}U`)
  if (p.cpu && (p.cpu.model || p.cpu.count != null || p.cpu.cores != null)) {
    const bits = [
      p.cpu.model || '',
      p.cpu.count != null ? `${p.cpu.count}颗` : '',
      p.cpu.cores != null ? `${p.cpu.cores}核` : '',
    ].filter(Boolean)
    if (bits.length) parts.push(`CPU ${bits.join(' ')}`)
  }
  if (p.memory && (p.memory.ddr_type || p.memory.stick_size_gb != null || p.memory.size_gb != null)) {
    const bits = [
      p.memory.ddr_type || '',
      p.memory.stick_size_gb != null ? `单条${p.memory.stick_size_gb}GB` : '',
      p.memory.size_gb != null ? `共${p.memory.size_gb}GB` : '',
    ].filter(Boolean)
    if (bits.length) parts.push(`内存 ${bits.join(' ')}`)
  }
  const disks = p.disks || []
  const sys = disks.filter((d) => d.role === 'system').map(formatDiskBrief).filter(Boolean)
  const cache = disks.filter((d) => d.role === 'cache').map(formatDiskBrief).filter(Boolean)
  const data = disks.filter((d) => d.role === 'data').map(formatDiskBrief).filter(Boolean)
  if (sys.length) parts.push(`系统盘 ${sys.join(' + ')}`)
  if (cache.length) parts.push(`缓存盘 ${cache.join(' + ')}`)
  if (data.length) parts.push(`数据盘 ${data.join(' + ')}`)
  if (p.nic) {
    const bits = [
      p.nic.ge_nic_count != null ? `千兆网卡${p.nic.ge_nic_count}` : '',
      p.nic.ge_port_count != null ? `千兆口${p.nic.ge_port_count}` : '',
      p.nic.xe_nic_count != null ? `万兆网卡${p.nic.xe_nic_count}` : '',
      p.nic.xe_port_count != null ? `万兆口${p.nic.xe_port_count}` : '',
      p.nic.onboard_type ? `板载${p.nic.onboard_type}` : '',
      p.nic.onboard_count != null ? `板载×${p.nic.onboard_count}` : '',
      p.nic.pcie_slot_count != null ? `PCIe×${p.nic.pcie_slot_count}` : '',
    ].filter(Boolean)
    if (bits.length) parts.push(`网络 ${bits.join(' / ')}`)
  }
  if (p.raid?.model) parts.push(`RAID ${p.raid.model}`)
  if (p.gpu && (p.gpu.model || p.gpu.count != null)) {
    const bits = [
      p.gpu.model || '',
      p.gpu.count != null ? `×${p.gpu.count}` : '',
      p.gpu.vram_gb != null ? `显存${p.gpu.vram_gb}GB` : '',
      p.gpu.bandwidth || '',
    ].filter(Boolean)
    if (bits.length) parts.push(`GPU ${bits.join(' ')}`)
  }
  if (p.switch) {
    const bits = [
      p.switch.switching_capacity || '',
      p.switch.forwarding_rate || '',
      p.switch.service_card_count != null ? `业务板${p.switch.service_card_count}` : '',
      p.switch.fabric_card_count != null ? `交换板${p.switch.fabric_card_count}` : '',
      p.switch.interface_card_count != null ? `接口卡${p.switch.interface_card_count}` : '',
      p.switch.interface_card_type ? `接口卡类型${p.switch.interface_card_type}` : '',
      p.switch.downlink_port_count != null ? `DOWN×${p.switch.downlink_port_count}` : '',
      p.switch.uplink_port_type ? `UP ${p.switch.uplink_port_type}` : '',
      p.switch.uplink_port_count != null ? `UP×${p.switch.uplink_port_count}` : '',
    ].filter(Boolean)
    if (bits.length) parts.push(`交换 ${bits.join(' / ')}`)
  }
  if (p.detail_params?.trim()) parts.push(p.detail_params.trim())
  if (p.other_params?.trim()) parts.push(p.other_params.trim())
  if (row.summary && !parts.length) return row.summary
  return parts.length ? parts.join('；') : '—'
}


async function ensureDeviceTypeOption(code: DeviceTypeCode) {
  const existed = deviceTypes.value.find((t) => t.code === code)
  if (existed) return existed
  const created = await createDeviceType({
    code,
    name: DEVICE_TYPE_FALLBACK_NAMES[code],
    description: DEVICE_TYPE_FALLBACK_NAMES[code],
  })
  deviceTypes.value = [...deviceTypes.value, created].sort((a, b) =>
    a.code.localeCompare(b.code),
  )
  return created
}

async function onParamDeviceTypePick(typeId: string | null) {
  if (!typeId) {
    form.device_type_id = ''
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

/** 将库中旧短名同步为与设备管理一致的标准名称，并补齐缺失类型 */
async function syncCanonicalDeviceTypes() {
  const byCode = new Map(deviceTypes.value.map((t) => [t.code, t]))
  for (const code of DEVICE_TYPE_CODES) {
    const want = DEVICE_TYPE_FALLBACK_NAMES[code]
    const hit = byCode.get(code)
    if (!hit) {
      try {
        const created = await createDeviceType({ code, name: want, description: want })
        deviceTypes.value = [...deviceTypes.value, created]
        byCode.set(code, created)
      } catch {
        // ignore
      }
      continue
    }
    if (hit.name !== want) {
      try {
        const updated = await updateDeviceType(hit.id, { name: want, description: want })
        deviceTypes.value = deviceTypes.value.map((t) => (t.id === updated.id ? updated : t))
        byCode.set(code, updated)
      } catch {
        // ignore
      }
    }
  }
}

function detailOf(row: ParamProfile) {
  return row.detail_params || row.payload?.detail_params || ''
}

function typeIdOf(row: ParamProfile) {
  return row.device_type_id || row.payload?.device_type_id || ''
}

function profileNameKey(row: ParamProfile) {
  return (row.source_device_name || row.payload?.source_device_name || row.name || '')
    .trim()
    .toLowerCase()
}

function isLinkedToSummary(row: ParamProfile) {
  const key = profileNameKey(row)
  return !!key && summaryNameKeys.value.has(key)
}

async function loadSummaryNames() {
  try {
    const summary = await getContractSummary()
    const keys = new Set<string>()
    for (const row of summary || []) {
      const name = (row.device_name || '').trim().toLowerCase()
      if (name) keys.add(name)
    }
    summaryNameKeys.value = keys
  } catch {
    summaryNameKeys.value = new Set()
  }
}

function legacyOtherParams(p: ParamProfilePayload): string {
  if (p.other_params?.trim()) return p.other_params
  const lines: string[] = []
  const fanBits = [
    p.fan_count != null ? `${p.fan_count}个` : '',
    p.fan_model || '',
  ].filter(Boolean)
  if (fanBits.length) lines.push(`风扇: ${fanBits.join(' ')}`)
  if (p.psu_power_w != null) lines.push(`电源: ${p.psu_power_w}W`)
  const raidBits = [p.raid?.model || '', p.raid?.params || ''].filter(Boolean)
  if (raidBits.length) lines.push(`RAID: ${raidBits.join(' / ')}`)
  if (p.supported_os?.length) lines.push(`操作系统: ${p.supported_os.join(', ')}`)
  return lines.join('\n')
}

function makeCode(deviceName: string): string {
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

function resetForm() {
  form.code = ''
  form.name = ''
  form.description = ''
  form.device_type_id = ''
  form.source_device_model = ''
  form.source_manufacturer = ''
  form.cpu_model = ''
  form.cpu_count = null
  form.cpu_cores = null
  form.memory_ddr = ''
  form.memory_stick_gb = null
  form.memory_total_gb = null
  form.systemDisk = emptyDisk('system')
  form.cacheDisk = emptyDisk('cache')
  form.dataDisks = [emptyDisk('data'), emptyDisk('data')]
  form.ge_nic_count = null
  form.ge_port_count = null
  form.xe_nic_count = null
  form.xe_port_count = null
  form.onboard_type = ''
  form.onboard_count = null
  form.pcie_slot_count = null
  form.raid_model = ''
  form.gpu_model = ''
  form.gpu_count = null
  form.gpu_vram_gb = null
  form.gpu_bandwidth = ''
  form.switching_capacity = ''
  form.forwarding_rate = ''
  form.service_card_count = null
  form.fabric_card_count = null
  form.interface_card_count = null
  form.interface_card_type = ''
  form.downlink_port_count = null
  form.uplink_port_type = ''
  form.uplink_port_count = null
  form.psu_power_w = null
  form.height_u = null
  form.other_params = ''
  editingPayload.value = null
}

function fillForm(row: ParamProfile) {
  const p = row.payload || {}
  editingPayload.value = p
  form.code = row.code
  form.name = row.name
  form.description = row.description || ''
  form.device_type_id = typeIdOf(row)
  form.source_device_model = modelOf(row)
  form.source_manufacturer = p.source_manufacturer || row.source_manufacturer || ''

  form.cpu_model = p.cpu?.model || ''
  form.cpu_count = p.cpu?.count ?? null
  form.cpu_cores = p.cpu?.cores ?? null
  form.memory_ddr = p.memory?.ddr_type || ''
  form.memory_stick_gb = p.memory?.stick_size_gb ?? null
  form.memory_total_gb = p.memory?.size_gb ?? null

  const disks = [...(p.disks || [])]
  const system = disks.find((d) => d.role === 'system')
  const cache = disks.find((d) => d.role === 'cache')
  const dataRows = disks.filter((d) => d.role === 'data')
  const legacy = disks.filter((d) => !d.role)
  if (system || cache || dataRows.length) {
    form.systemDisk = system
      ? { ...emptyDisk('system'), ...system, role: 'system' }
      : emptyDisk('system')
    form.cacheDisk = cache
      ? { ...emptyDisk('cache'), ...cache, role: 'cache' }
      : emptyDisk('cache')
    form.dataDisks = dataRows.length
      ? dataRows.map((d) => ({ ...emptyDisk('data'), ...d, role: 'data' as const }))
      : [emptyDisk('data'), emptyDisk('data')]
  } else if (legacy.length) {
    form.systemDisk = { ...emptyDisk('system'), ...legacy[0], role: 'system' }
    form.cacheDisk = emptyDisk('cache')
    form.dataDisks = legacy.slice(1).length
      ? legacy.slice(1).map((d) => ({ ...emptyDisk('data'), ...d, role: 'data' as const }))
      : [emptyDisk('data'), emptyDisk('data')]
  } else {
    form.systemDisk = emptyDisk('system')
    form.cacheDisk = emptyDisk('cache')
    form.dataDisks = [emptyDisk('data'), emptyDisk('data')]
  }

  form.ge_nic_count = p.nic?.ge_nic_count ?? null
  form.ge_port_count = p.nic?.ge_port_count ?? null
  form.xe_nic_count = p.nic?.xe_nic_count ?? null
  form.xe_port_count = p.nic?.xe_port_count ?? null
  form.onboard_type = p.nic?.onboard_type || ''
  form.onboard_count = p.nic?.onboard_count ?? null
  form.pcie_slot_count = p.nic?.pcie_slot_count ?? null
  form.raid_model = p.raid?.model || ''
  form.gpu_model = p.gpu?.model || ''
  form.gpu_count = p.gpu?.count ?? null
  form.gpu_vram_gb = p.gpu?.vram_gb ?? null
  form.gpu_bandwidth = p.gpu?.bandwidth || ''
  form.switching_capacity = p.switch?.switching_capacity || ''
  form.forwarding_rate = p.switch?.forwarding_rate || ''
  form.service_card_count = p.switch?.service_card_count ?? null
  form.fabric_card_count = p.switch?.fabric_card_count ?? null
  form.interface_card_count = p.switch?.interface_card_count ?? null
  form.interface_card_type = p.switch?.interface_card_type || ''
  form.downlink_port_count = p.switch?.downlink_port_count ?? null
  form.uplink_port_type = p.switch?.uplink_port_type || ''
  form.uplink_port_count = p.switch?.uplink_port_count ?? null
  form.psu_power_w = p.psu_power_w ?? null
  form.height_u = p.height_u ?? null
  form.other_params = legacyOtherParams(p)
}

function packDisk(disk: ParamDiskSpec, role: DiskRole): ParamDiskSpec | null {
  if (!isDiskRowFilled(disk)) return null
  return {
    size_gb: disk.size_gb,
    count: disk.count,
    interface: disk.interface || null,
    media_type: disk.media_type || null,
    role,
  }
}

function buildPayload(): ParamProfilePayload {
  const disks: ParamDiskSpec[] = []
  const system = packDisk(form.systemDisk, 'system')
  const cache = packDisk(form.cacheDisk, 'cache')
  const dataDisks = form.dataDisks
    .map((d) => packDisk(d, 'data'))
    .filter((d): d is ParamDiskSpec => !!d)
  if (system) disks.push(system)
  else disks.push({ role: 'system' })
  if (cache) disks.push(cache)
  if (dataDisks.length) disks.push(...dataDisks)
  else disks.push({ role: 'data' })

  const prev = editingPayload.value
  const hasCpu = !!(form.cpu_model.trim() || form.cpu_count != null || form.cpu_cores != null)
  const hasMem = !!(
    form.memory_ddr.trim() ||
    form.memory_stick_gb != null ||
    form.memory_total_gb != null
  )
  const hasNic = [
    form.ge_nic_count,
    form.ge_port_count,
    form.xe_nic_count,
    form.xe_port_count,
    form.onboard_count,
    form.pcie_slot_count,
  ].some((v) => v != null) || !!form.onboard_type.trim()
  const hasGpu = !!(
    form.gpu_model.trim() ||
    form.gpu_count != null ||
    form.gpu_vram_gb != null ||
    form.gpu_bandwidth.trim()
  )
  const hasSwitch = !!(
    form.switching_capacity.trim() ||
    form.forwarding_rate.trim() ||
    form.service_card_count != null ||
    form.fabric_card_count != null ||
    form.interface_card_count != null ||
    form.interface_card_type.trim() ||
    form.downlink_port_count != null ||
    form.uplink_port_type.trim() ||
    form.uplink_port_count != null
  )

  return {
    source_device_name: form.name || null,
    source_device_model: form.source_device_model.trim() || null,
    source_manufacturer: form.source_manufacturer.trim() || null,
    device_type_id: form.device_type_id || null,
    detail_params: prev?.detail_params ?? null,
    other_params: form.other_params.trim() || null,
    cpu: hasCpu
      ? {
          model: form.cpu_model.trim() || null,
          count: form.cpu_count,
          cores: form.cpu_cores,
          architecture: prev?.cpu?.architecture ?? null,
        }
      : null,
    memory: hasMem
      ? {
          ddr_type: form.memory_ddr.trim() || null,
          stick_size_gb: form.memory_stick_gb,
          size_gb: form.memory_total_gb,
          modules: prev?.memory?.modules ?? null,
        }
      : null,
    disks,
    nic: hasNic
      ? {
          ge_nic_count: form.ge_nic_count,
          ge_port_count: form.ge_port_count,
          xe_nic_count: form.xe_nic_count,
          xe_port_count: form.xe_port_count,
          onboard_type: form.onboard_type.trim() || null,
          onboard_count: form.onboard_count,
          pcie_slot_count: form.pcie_slot_count,
        }
      : null,
    gpu: hasGpu
      ? {
          model: form.gpu_model.trim() || null,
          count: form.gpu_count,
          vram_gb: form.gpu_vram_gb,
          bandwidth: form.gpu_bandwidth.trim() || null,
        }
      : null,
    switch: hasSwitch
      ? {
          switching_capacity: form.switching_capacity.trim() || null,
          forwarding_rate: form.forwarding_rate.trim() || null,
          service_card_count: form.service_card_count,
          fabric_card_count: form.fabric_card_count,
          interface_card_count: form.interface_card_count,
          interface_card_type: form.interface_card_type.trim() || null,
          downlink_port_count: form.downlink_port_count,
          uplink_port_type: form.uplink_port_type.trim() || null,
          uplink_port_count: form.uplink_port_count,
        }
      : null,
    fan_count: prev?.fan_count ?? null,
    fan_model: prev?.fan_model ?? null,
    psu_power_w: form.psu_power_w,
    height_u: form.height_u,
    raid: form.raid_model.trim()
      ? { model: form.raid_model.trim(), params: prev?.raid?.params ?? null }
      : prev?.raid ?? null,
    supported_os: prev?.supported_os?.length ? [...prev.supported_os] : [],
    custom: prev?.custom?.length ? [...prev.custom] : [],
  }
}

function addDataDiskRow() {
  if (form.dataDisks.length >= MAX_DISK_SPEC_COUNT - 1) {
    ElMessage.warning(`最多添加 ${MAX_DISK_SPEC_COUNT - 1} 种数据盘规格`)
    return
  }
  form.dataDisks.push(emptyDisk('data'))
}

function removeDataDiskRow(idx: number) {
  if (form.dataDisks.length <= 1) {
    form.dataDisks[0] = emptyDisk('data')
    return
  }
  form.dataDisks.splice(idx, 1)
}

const manufacturerOptions = computed(() => {
  const set = new Set<string>()
  for (const row of profiles.value) {
    const m = row.source_manufacturer || row.payload?.source_manufacturer
    if (m) set.add(m)
  }
  return [...set].sort()
})

const filteredProfiles = computed(() => {
  const kw = filters.keyword.trim().toLowerCase()
  return profiles.value.filter((row) => {
    if (filters.status === 'complete' && !row.is_complete) return false
    if (filters.status === 'incomplete' && row.is_complete) return false
    if (filters.manufacturer) {
      const m = row.source_manufacturer || row.payload?.source_manufacturer || ''
      if (m !== filters.manufacturer) return false
    }
    if (filters.device_type_id && typeIdOf(row) !== filters.device_type_id) return false
    if (!kw) return true
    const hay = [
      row.name,
      modelOf(row),
      detailOf(row),
      deviceTypeName(typeIdOf(row)),
      row.source_manufacturer,
      row.summary,
      row.description,
      ...(row.missing_fields || []),
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return hay.includes(kw)
  })
})

const stats = computed(() => {
  const total = profiles.value.length
  const incomplete = profiles.value.filter((p) => !p.is_complete).length
  return { total, incomplete, complete: total - incomplete }
})

function rowClassName({ row }: { row: ParamProfile }) {
  return row.is_complete ? 'row-complete' : 'row-incomplete'
}

async function loadDeviceTypes() {
  try {
    deviceTypes.value = await listDeviceTypes()
    await syncCanonicalDeviceTypes()
  } catch {
    deviceTypes.value = []
  }
}

async function loadData(opts?: { silent?: boolean }) {
  loading.value = true
  try {
    const [list] = await Promise.all([listParamProfiles(), loadSummaryNames()])
    profiles.value = list
  } catch {
    profiles.value = []
    if (!opts?.silent) ElMessage.error('加载设备参数失败')
  } finally {
    loading.value = false
  }
}

async function handleSync() {
  syncing.value = true
  try {
    const result = await syncParamProfilesFromContracts()
    if (result.total_summary === 0) {
      ElMessage.warning('采购汇总中暂无设备名称可同步')
    } else if (result.created === 0 && result.updated === 0 && result.skipped > 0) {
      ElMessage.info(`采购汇总设备名称均已关联，已对齐 ${result.skipped} 项`)
    } else {
      const parts = [
        result.created ? `新建 ${result.created}` : '',
        result.updated ? `同步 ${result.updated}` : '',
        result.skipped ? `已对齐 ${result.skipped}` : '',
      ].filter(Boolean)
      ElMessage.success(`关联同步完成：${parts.join('，')}`)
    }
    await loadData({ silent: true })
  } catch (error: unknown) {
    const err = error as {
      response?: { status?: number; data?: { message?: string } }
      message?: string
    }
    const detail = err.response?.data?.message || err.message
    ElMessage.error(detail ? `同步采购汇总失败：${detail}` : '同步采购汇总失败')
  } finally {
    syncing.value = false
  }
}

async function handleExport(incompleteOnly: boolean) {
  exporting.value = true
  try {
    await exportParamProfiles(incompleteOnly)
    ElMessage.success(incompleteOnly ? '已导出未完善参数' : '已导出全部参数')
  } catch {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

async function handleDownloadTemplate() {
  try {
    await downloadParamProfilesTemplate()
  } catch {
    ElMessage.error('模板下载失败')
  }
}

function triggerImport() {
  importInput.value?.click()
}

async function handleImportFile(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  importing.value = true
  try {
    const result = await importParamProfiles(file)
    const errHint = result.errors?.length ? `；错误 ${result.errors.length} 条` : ''
    ElMessage.success(
      `导入完成：更新 ${result.updated}，新建 ${result.created}，跳过 ${result.skipped}${errHint}`,
    )
    if (result.errors?.length) {
      console.warn('参数导入错误', result.errors)
    }
    await loadData({ silent: true })
  } catch {
    ElMessage.error('导入失败')
  } finally {
    importing.value = false
  }
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: ParamProfile) {
  editingId.value = row.id
  fillForm(row)
  dialogVisible.value = true
}

function openView(row: ParamProfile) {
  detailProfile.value = row
  detailVisible.value = true
}

/** 新建时若尚未手填设备参数ID，随名称自动生成建议值 */
function onNameChangeForCode() {
  if (editingId.value) return
  const name = form.name.trim()
  if (!name) return
  if (!form.code.trim()) {
    form.code = makeCode(name)
  }
}

async function handleSave() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写设备名称')
    return
  }
  const code = form.code.trim() || makeCode(form.name.trim())
  if (!code) {
    ElMessage.warning('请填写设备参数ID')
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    if (editingId.value) {
      await updateParamProfile(editingId.value, {
        code,
        name: form.name.trim(),
        payload,
        description: form.description || null,
      })
    } else {
      await createParamProfile({
        code,
        name: form.name.trim(),
        payload,
        description: form.description || null,
      })
    }
    ElMessage.success('设备参数已保存')
    dialogVisible.value = false
    await loadData({ silent: true })
  } catch (error: unknown) {
    const err = error as {
      response?: { data?: { message?: string } }
      message?: string
    }
    ElMessage.error(err.response?.data?.message || err.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: ParamProfile) {
  await ElMessageBox.confirm(`确定删除设备参数「${row.name}」吗？`, '确认删除', { type: 'warning' })
  await deleteParamProfile(row.id)
  ElMessage.success('已删除')
  await loadData({ silent: true })
}

onMounted(async () => {
  await Promise.all([loadData(), loadDeviceTypes()])
  applyRouteQuery()
  if (canUpdate) {
    try {
      const result = await syncParamProfilesFromContracts()
      if (result.created > 0 || result.updated > 0) {
        await loadData({ silent: true })
      }
    } catch {
      /* 采购汇总为空或无权限时忽略自动同步 */
    }
  }
})

function applyRouteQuery() {
  const kw = String(route.query.keyword || '').trim()
  if (kw) filters.keyword = kw
  const profileId = String(route.query.profile_id || '').trim()
  if (profileId) {
    const hit = profiles.value.find((p) => p.id === profileId)
    if (hit) openView(hit)
  }
}

watch(
  () => [route.query.keyword, route.query.profile_id],
  () => applyRouteQuery(),
)
</script>

<template>
  <div class="param-panel">
    <div class="stats-bar">
      <span>共 {{ stats.total }} 项</span>
      <span class="stat-incomplete">待完善 {{ stats.incomplete }}</span>
      <span class="stat-complete">已完善 {{ stats.complete }}</span>
      <span class="hint">
        与资产汇总按「设备名称」关联同步：缺则新建、同名则对齐设备名称 / 产品型号 / 产品厂商
      </span>
    </div>

    <div class="toolbar">
      <el-input
        v-model="filters.keyword"
        clearable
        size="small"
        placeholder="搜索设备名称 / 产品型号 / 设备类型 / 摘要"
        style="width: 260px"
      />
      <el-select v-model="filters.status" size="small" style="width: 120px">
        <el-option label="全部状态" value="all" />
        <el-option label="待完善" value="incomplete" />
        <el-option label="已完善" value="complete" />
      </el-select>
      <el-select
        v-model="filters.device_type_id"
        clearable
        size="small"
        placeholder="设备类型"
        style="width: 160px"
      >
        <el-option
          v-for="t in deviceTypeOptions.filter((o) => o.id)"
          :key="t.code"
          :label="t.name"
          :value="t.id"
        />
      </el-select>
      <el-select
        v-model="filters.manufacturer"
        clearable
        size="small"
        placeholder="产品厂商"
        style="width: 130px"
      >
        <el-option v-for="m in manufacturerOptions" :key="m" :label="m" :value="m" />
      </el-select>
      <el-button size="small" :loading="loading" @click="loadData()">刷新</el-button>
      <el-button
        v-if="canUpdate || canCreate"
        size="small"
        type="primary"
        plain
        :loading="syncing"
        @click="handleSync"
      >
        同步采购汇总
      </el-button>
      <el-dropdown v-if="canUpdate || canCreate" trigger="click" @command="(c: string) => handleExport(c === 'incomplete')">
        <el-button size="small" :loading="exporting">导出 Excel</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="incomplete">仅未完善参数</el-dropdown-item>
            <el-dropdown-item command="all">全部参数</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-button size="small" @click="handleDownloadTemplate">下载模板</el-button>
      <el-button
        v-if="canUpdate || canCreate"
        size="small"
        :loading="importing"
        @click="triggerImport"
      >
        导入更新
      </el-button>
      <el-button v-if="canCreate || canUpdate" type="primary" size="small" @click="openCreate">
        手动新建
      </el-button>
      <input
        ref="importInput"
        type="file"
        accept=".xlsx,.xls"
        style="display: none"
        @change="handleImportFile"
      />
    </div>

    <div class="table-panel">
      <el-table
        v-loading="loading"
        :data="filteredProfiles"
        stripe
        size="small"
        height="100%"
        class="sheet-table"
        :row-class-name="rowClassName"
      >
        <el-table-column type="selection" width="40" />
        <el-table-column
          type="index"
          label="序号"
          width="56"
          align="center"
          :index="(i: number) => i + 1"
        />
        <el-table-column prop="code" label="设备参数ID" min-width="140" show-overflow-tooltip />
        <el-table-column prop="name" label="设备名称" min-width="120" show-overflow-tooltip />
        <el-table-column label="产品型号" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ modelOf(row) || '—' }}</template>
        </el-table-column>
        <el-table-column label="产品厂商" min-width="100" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.source_manufacturer || row.payload?.source_manufacturer || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="设备类型" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ deviceTypeName(typeIdOf(row)) }}</template>
        </el-table-column>
        <el-table-column label="类型归类" min-width="100" show-overflow-tooltip>
          <template #default="{ row }">{{ typeClassOf(row) }}</template>
        </el-table-column>
        <el-table-column label="配置参数" min-width="320">
          <template #default="{ row }">
            <div class="config-cell" :title="configParamsOf(row)">{{ configParamsOf(row) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right" align="center">
          <template #default="{ row }">
            <el-dropdown trigger="click">
              <el-button type="primary" link>操作</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="openView(row)">查看参数详细</el-dropdown-item>
                  <el-dropdown-item v-if="canUpdate" @click="openEdit(row)">编辑</el-dropdown-item>
                  <el-dropdown-item v-if="canDelete" divided @click="handleDelete(row)">删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <ParamProfileDetailDialog
      v-model="detailVisible"
      :profile="detailProfile"
      :device-types="deviceTypes"
    />

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑设备参数' : '新建设备参数'"
      width="1120px"
      destroy-on-close
      top="2vh"
      class="param-sheet-dialog"
    >
      <div class="param-sheet">
        <!-- 基本信息 -->
        <section class="sheet-block">
          <div class="sheet-side">基本信息</div>
          <div class="sheet-body">
            <div class="sheet-row cols-3">
              <label>设备名称</label>
              <el-input
                v-model="form.name"
                placeholder="采购/管理中的设备名称"
                @change="onNameChangeForCode"
              />
              <label>产品型号</label>
              <el-input v-model="form.source_device_model" placeholder="产品型号" />
              <label>产品厂商</label>
              <el-input v-model="form.source_manufacturer" placeholder="产品厂商" />
            </div>
            <div class="sheet-row cols-3">
              <label>设备类型</label>
              <el-select
                :model-value="form.device_type_id || undefined"
                clearable
                filterable
                placeholder="选择设备类型"
                @change="onParamDeviceTypePick"
              >
                <el-option
                  v-for="t in deviceTypeOptions"
                  :key="t.code"
                  :label="t.name"
                  :value="t.id || t.code"
                />
              </el-select>
            </div>
          </div>
        </section>

        <!-- 参数配置 -->
        <section class="sheet-block">
          <div class="sheet-side">参数配置</div>
          <div class="sheet-body">
            <div class="sheet-row cols-3">
              <label>电源功率</label>
              <el-input-number
                v-model="form.psu_power_w"
                :min="0"
                :step="100"
                controls-position="right"
                placeholder="W"
              />
              <label>设备高度</label>
              <el-input-number
                v-model="form.height_u"
                :min="1"
                :max="48"
                controls-position="right"
                placeholder="U"
              />
            </div>
            <div class="sheet-row cols-3">
              <label>CPU型号</label>
              <el-input v-model="form.cpu_model" placeholder="如 Intel Xeon Gold 6330" />
              <label>颗数</label>
              <el-input-number v-model="form.cpu_count" :min="0" :max="64" controls-position="right" />
              <label>核心数</label>
              <el-input-number v-model="form.cpu_cores" :min="1" :max="512" controls-position="right" />
            </div>
            <div class="sheet-row cols-3">
              <label>内存型号</label>
              <el-select v-model="form.memory_ddr" clearable filterable allow-create placeholder="DDR4/5">
                <el-option v-for="o in MEMORY_TYPE_OPTIONS" :key="o" :label="o" :value="o" />
              </el-select>
              <label>单条内存大小</label>
              <el-input-number
                v-model="form.memory_stick_gb"
                :min="0"
                :step="8"
                controls-position="right"
                placeholder="GB"
              />
              <label>总内存大小</label>
              <el-input-number
                v-model="form.memory_total_gb"
                :min="0"
                :step="16"
                controls-position="right"
                placeholder="GB"
              />
            </div>

            <div class="sheet-row cols-4 disk-line">
              <label class="role-label">系统盘大小</label>
              <el-input-number v-model="form.systemDisk.size_gb" :min="0" :step="100" controls-position="right" />
              <label>磁盘数量</label>
              <el-input-number v-model="form.systemDisk.count" :min="0" :max="100" controls-position="right" />
              <label>磁盘接口</label>
              <el-select v-model="form.systemDisk.interface" clearable filterable allow-create>
                <el-option v-for="i in DISK_INTERFACE_OPTIONS" :key="i" :label="i" :value="i" />
              </el-select>
              <label>磁盘类型</label>
              <el-select v-model="form.systemDisk.media_type" clearable>
                <el-option v-for="m in DISK_MEDIA_OPTIONS" :key="m.value" :label="m.label" :value="m.value" />
              </el-select>
            </div>
            <div class="sheet-row cols-4 disk-line">
              <label class="role-label">缓存盘大小</label>
              <el-input-number v-model="form.cacheDisk.size_gb" :min="0" :step="100" controls-position="right" />
              <label>磁盘数量</label>
              <el-input-number v-model="form.cacheDisk.count" :min="0" :max="100" controls-position="right" />
              <label>磁盘接口</label>
              <el-select v-model="form.cacheDisk.interface" clearable filterable allow-create>
                <el-option v-for="i in DISK_INTERFACE_OPTIONS" :key="i" :label="i" :value="i" />
              </el-select>
              <label>磁盘类型</label>
              <el-select v-model="form.cacheDisk.media_type" clearable>
                <el-option v-for="m in DISK_MEDIA_OPTIONS" :key="m.value" :label="m.label" :value="m.value" />
              </el-select>
            </div>

            <div
              v-for="(disk, idx) in form.dataDisks"
              :key="`data-${idx}`"
              class="sheet-row cols-4 disk-line"
            >
              <label class="role-label">数据盘·规格{{ idx + 1 }}</label>
              <el-input-number v-model="disk.size_gb" :min="0" :step="100" controls-position="right" />
              <label>磁盘数量</label>
              <el-input-number v-model="disk.count" :min="0" :max="100" controls-position="right" />
              <label>磁盘接口</label>
              <el-select v-model="disk.interface" clearable filterable allow-create>
                <el-option v-for="i in DISK_INTERFACE_OPTIONS" :key="i" :label="i" :value="i" />
              </el-select>
              <label>磁盘类型</label>
              <div class="inline-actions">
                <el-select v-model="disk.media_type" clearable style="flex: 1">
                  <el-option v-for="m in DISK_MEDIA_OPTIONS" :key="m.value" :label="m.label" :value="m.value" />
                </el-select>
                <el-button v-if="form.dataDisks.length > 1" link type="danger" @click="removeDataDiskRow(idx)">
                  删
                </el-button>
                <el-button
                  v-if="idx === form.dataDisks.length - 1"
                  link
                  type="primary"
                  @click="addDataDiskRow"
                >
                  添加规格
                </el-button>
              </div>
            </div>

            <div class="sheet-row cols-4">
              <label>千兆网卡数量</label>
              <el-input-number v-model="form.ge_nic_count" :min="0" :max="64" controls-position="right" />
              <label>千兆接口数量</label>
              <el-input-number v-model="form.ge_port_count" :min="0" :max="256" controls-position="right" />
              <label>万兆网卡数量</label>
              <el-input-number v-model="form.xe_nic_count" :min="0" :max="64" controls-position="right" />
              <label>万兆接口数量</label>
              <el-input-number v-model="form.xe_port_count" :min="0" :max="256" controls-position="right" />
            </div>
            <div class="sheet-row cols-4">
              <label>板载接口类型</label>
              <el-select v-model="form.onboard_type" clearable filterable allow-create>
                <el-option v-for="o in ONBOARD_TYPE_OPTIONS" :key="o" :label="o" :value="o" />
              </el-select>
              <label>板载接口数量</label>
              <el-input-number v-model="form.onboard_count" :min="0" :max="256" controls-position="right" />
              <label>PCIe插槽数量</label>
              <el-input-number v-model="form.pcie_slot_count" :min="0" :max="64" controls-position="right" />
              <label>RAID卡型号</label>
              <el-input v-model="form.raid_model" placeholder="如 RAID9460" />
            </div>
            <div class="sheet-row cols-4">
              <label>显卡型号</label>
              <el-input v-model="form.gpu_model" placeholder="如 NVIDIA A100" />
              <label>显卡个数</label>
              <el-input-number v-model="form.gpu_count" :min="0" :max="64" controls-position="right" />
              <label>显存大小</label>
              <el-input-number v-model="form.gpu_vram_gb" :min="0" :step="8" controls-position="right" placeholder="GB" />
              <label>显存带宽</label>
              <el-input v-model="form.gpu_bandwidth" placeholder="如 2039GB/s" />
            </div>
          </div>
        </section>

        <!-- 网络参数 -->
        <section class="sheet-block">
          <div class="sheet-side">网络参数</div>
          <div class="sheet-body">
            <div class="sheet-row cols-4">
              <label>交换容量</label>
              <el-input v-model="form.switching_capacity" placeholder="如 2.56Tbps" />
              <label>包转发率</label>
              <el-input v-model="form.forwarding_rate" placeholder="如 1920Mpps" />
              <label>业务板卡数量</label>
              <el-input-number v-model="form.service_card_count" :min="0" :max="256" controls-position="right" />
              <label>交换板卡数量</label>
              <el-input-number v-model="form.fabric_card_count" :min="0" :max="256" controls-position="right" />
            </div>
            <div class="sheet-row cols-3">
              <label>接口卡数量</label>
              <el-input-number
                v-model="form.interface_card_count"
                :min="0"
                :max="256"
                controls-position="right"
              />
              <label>接口卡类型</label>
              <el-select
                v-model="form.interface_card_type"
                clearable
                placeholder="400G / 100G / 40G / 25G / 10G / 1G"
              >
                <el-option
                  v-for="o in INTERFACE_CARD_TYPE_OPTIONS"
                  :key="o"
                  :label="o"
                  :value="o"
                />
              </el-select>
              <label>DOWNLINK接口个数</label>
              <el-input-number
                v-model="form.downlink_port_count"
                :min="0"
                :max="1024"
                controls-position="right"
              />
            </div>
            <div class="sheet-row cols-3">
              <label>UPLINK上联接口类型</label>
              <el-select
                v-model="form.uplink_port_type"
                clearable
                placeholder="400G / 100G / 40G / 25G / 10G"
              >
                <el-option
                  v-for="o in UPLINK_PORT_TYPE_OPTIONS"
                  :key="o"
                  :label="o"
                  :value="o"
                />
              </el-select>
              <label>UPLINK上联接口个数</label>
              <el-input-number
                v-model="form.uplink_port_count"
                :min="0"
                :max="1024"
                controls-position="right"
              />
            </div>
          </div>
        </section>

        <!-- 其他参数 -->
        <section class="sheet-block">
          <div class="sheet-side">其他参数</div>
          <div class="sheet-body">
            <div class="sheet-row cols-1">
              <label>手动输入</label>
              <el-input
                v-model="form.other_params"
                type="textarea"
                :rows="2"
                maxlength="3000"
                show-word-limit
                placeholder="补充风扇、电源、操作系统等非结构化说明"
              />
            </div>
          </div>
        </section>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.param-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: calc(100vh - 220px);
  min-height: 420px;
}

.stats-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  font-size: 12px;
  color: #5b6b7c;
  flex-shrink: 0;
}

.stat-incomplete {
  color: #c45656;
  font-weight: 600;
}

.stat-complete {
  color: #303133;
  font-weight: 600;
}

.hint {
  color: #8a97a8;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}

.text-incomplete {
  color: #c45656;
}

.text-complete {
  color: #303133;
}

:deep(.row-incomplete td) {
  color: #c45656;
}

:deep(.row-complete td) {
  color: #303133;
}

.table-panel {
  flex: 1;
  min-height: 0;
  border: 1px solid #8aa0b8;
  background: #e8f0f8;
  overflow: hidden;
}

.sheet-table {
  --el-table-header-bg-color: #c8d8ea;
  --el-table-header-text-color: #1f2a37;
  --el-table-bg-color: #eef4fb;
  --el-table-tr-bg-color: #eef4fb;
  --el-table-row-hover-bg-color: #dce8f7;
  --el-table-border-color: #8aa0b8;
}

.config-cell {
  white-space: normal;
  line-height: 1.45;
  font-size: 12px;
  color: #1f2a37;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

.param-form {
  max-height: 72vh;
  overflow-y: auto;
  padding-right: 8px;
}

.param-sheet {
  max-height: 74vh;
  overflow: auto;
  padding: 10px;
  background: #c5d6ea;
  border: 1px solid #7f94ab;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sheet-block {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 0;
  background: #e8f0f8;
  border: 1px solid #8aa0b8;
}

.sheet-side {
  display: flex;
  align-items: center;
  justify-content: center;
  writing-mode: vertical-rl;
  letter-spacing: 0.18em;
  font-size: 13px;
  font-weight: 700;
  color: #1f2a37;
  background: #d7e4f2;
  border-right: 1px solid #8aa0b8;
  padding: 10px 0;
}

.sheet-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
}

.sheet-row {
  display: grid;
  align-items: center;
  gap: 6px 8px;
}

.sheet-row.cols-1 {
  grid-template-columns: 88px 1fr;
}

.sheet-row.cols-3 {
  grid-template-columns: 88px 1fr 72px 1fr 88px 1fr;
}

.sheet-row.cols-4 {
  grid-template-columns: 96px 1fr 72px 0.8fr 72px 0.9fr 72px 0.9fr;
}

.sheet-row label {
  justify-self: end;
  font-size: 12px;
  color: #1f2937;
  white-space: nowrap;
}

.sheet-row .role-label {
  font-weight: 600;
}

.sheet-row :deep(.el-input),
.sheet-row :deep(.el-select),
.sheet-row :deep(.el-input-number) {
  width: 100%;
}

.inline-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

@media (max-width: 1100px) {
  .sheet-row.cols-3,
  .sheet-row.cols-4 {
    grid-template-columns: 96px 1fr 88px 1fr;
  }
}

</style>
