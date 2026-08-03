<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  batchMountDevices,
  createDeviceModel,
  createDeviceType,
  type BatchMountNewDevice,
  type DeviceModel,
  type DeviceType,
} from '@/api/device'
import {
  listIpAddresses,
  listIpSegments,
  type IpAddress,
  type IpSegment,
} from '@/api/ip'
import type { Rack } from '@/api/rack'
import { listRacks } from '@/api/rack'
import type { Room } from '@/api/room'
import {
  contractItemKey,
  findContractItem,
  type DeviceContract,
  type DeviceContractItem,
} from '@/api/contract'
import RackRangePicker from '@/components/RackRangePicker.vue'

const props = defineProps<{
  modelValue: boolean
  rooms: Room[]
  racks: Rack[]
  models: DeviceModel[]
  types: DeviceType[]
  contracts?: DeviceContract[]
}>()

const emit = defineEmits<{
  'update:modelValue': [boolean]
  success: []
  'type-created': [DeviceType]
  'model-created': [DeviceModel]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const step = ref(0)
const submitting = ref(false)
const ipLoading = ref(false)
const segmentLoading = ref(false)
const segmentIpsLoading = ref(false)

/** 全局空闲 IP（供范围文本应用，懒加载） */
const allFreeIps = ref<IpAddress[]>([])
const ipSegments = ref<IpSegment[]>([])
const activeSegmentId = ref<string | null>(null)
const segmentIps = ref<IpAddress[]>([])
/** 段内空闲 IP 缓存，切换地址段时秒开 */
const segmentIpCache = new Map<string, IpAddress[]>()
let segmentLoadSeq = 0
let freeIpLoadPromise: Promise<void> | null = null

const pickKind = ref<'business' | 'bmc'>('business')
const selectedBusinessIpIds = ref<string[]>([])
const selectedBmcIpIds = ref<string[]>([])
const businessIpRangeText = ref('')
const bmcIpRangeText = ref('')
const businessIpRangeError = ref('')
const bmcIpRangeError = ref('')
const ipTableRef = ref<{
  clearSelection: () => void
  toggleRowSelection: (row: IpAddress, selected?: boolean) => void
} | null>(null)
const syncingTableSelection = ref(false)

const form = reactive({
  count: 4,
  name_prefix: 'SRV',
  serial_prefix: 'SN',
  start_index: 1,
  device_model_id: '',
  device_type_id: '' as string | null,
  height_u: 1 as number | null,
  contract_id: '' as string | null,
  contract_item_key: '',
  room_id: '',
  rack_ids: [] as string[],
  start_u: 1,
  gap_u: 1,
  per_rack_count: 1,
})

const previewRows = ref<BatchMountNewDevice[]>([])
const previewLines = ref<string[]>([])
/** 上架步骤拉取的最新机柜占用（含 device_count / free_u） */
const mountRacks = ref<Rack[]>([])
const mountRacksLoading = ref(false)

const selectedContract = computed(
  () => (props.contracts || []).find((c) => c.id === form.contract_id) || null,
)

const contractItems = computed((): DeviceContractItem[] => {
  const items = selectedContract.value?.device_items
  return Array.isArray(items) ? items.filter((it) => it.device_name) : []
})

const selectedContractItem = computed(() =>
  findContractItem(selectedContract.value, form.contract_item_key),
)

const roomRacks = computed(() => {
  const source = mountRacks.value.length ? mountRacks.value : props.racks
  return source.filter((r) => r.room_id === form.room_id)
})

const targetRacks = computed(() => {
  if (!form.room_id) return [] as Rack[]
  if (form.rack_ids.length) {
    return roomRacks.value.filter((r) => form.rack_ids.includes(r.id))
  }
  return roomRacks.value
})

const needCount = computed(() => Math.max(1, form.count || 1))

const rackOccupancySummary = computed(() => {
  const racks = targetRacks.value
  if (!racks.length) {
    return { occupiedRacks: 0, totalDevices: 0, totalFreeU: 0, insufficient: [] as string[] }
  }
  const heightU = Math.max(1, form.height_u || 1)
  const occupiedRacks = racks.filter((r) => (r.device_count ?? 0) > 0 || (r.occupied_u ?? 0) > 0)
  const totalDevices = racks.reduce((s, r) => s + (r.device_count ?? 0), 0)
  const totalFreeU = racks.reduce((s, r) => s + (r.free_u ?? 0), 0)
  const insufficient = racks
    .filter((r) => (r.free_u ?? 0) < heightU)
    .map((r) => r.code)
  return {
    occupiedRacks: occupiedRacks.length,
    totalDevices,
    totalFreeU,
    insufficient,
  }
})

const unboundFreeIps = computed(() =>
  allFreeIps.value
    .filter((ip) => isSelectableIp(ip))
    .slice()
    .sort((a, b) => ipToNum(a.system_ip) - ipToNum(b.system_ip)),
)

/** 勾选列表只展示空闲地址，避免大段全量渲染卡顿 */
const segmentFreeIps = computed(() =>
  segmentIps.value
    .filter((ip) => isSelectableIp(ip))
    .slice()
    .sort((a, b) => ipToNum(a.system_ip) - ipToNum(b.system_ip)),
)

const segmentListIps = computed(() => segmentFreeIps.value)

const activeSegment = computed(
  () => ipSegments.value.find((s) => s.id === activeSegmentId.value) || null,
)

const selectedBusinessIps = computed(() =>
  resolveSelectedIps(selectedBusinessIpIds.value),
)

const selectedBmcIps = computed(() => resolveSelectedIps(selectedBmcIpIds.value))

const activeSelectedIds = computed({
  get: () =>
    pickKind.value === 'business' ? selectedBusinessIpIds.value : selectedBmcIpIds.value,
  set: (ids: string[]) => {
    if (pickKind.value === 'business') selectedBusinessIpIds.value = ids
    else selectedBmcIpIds.value = ids
  },
})

const otherSelectedIds = computed(() =>
  pickKind.value === 'business' ? selectedBmcIpIds.value : selectedBusinessIpIds.value,
)

const otherSelectedIdSet = computed(() => new Set(otherSelectedIds.value))
const activeSelectedIdSet = computed(() => new Set(activeSelectedIds.value))

const selectedIpSummary = computed(() => {
  const biz = selectedBusinessIpIds.value.length
  const bmc = selectedBmcIpIds.value.length
  if (!biz && !bmc) return '未选择业务/BMC 地址（可跳过，后续再关联）'
  return `业务IP ${biz}/${needCount.value} · BMC地址 ${bmc}/${needCount.value}`
})

/** 按空闲 U / 起始 U / 间隔估算每柜可上架台数（取目标机柜最小值） */
const suggestedPerRackCount = computed(() => {
  const heightU = Math.max(1, form.height_u || 1)
  const gapU = Math.max(0, form.gap_u || 0)
  const startU = Math.max(1, form.start_u || 1)
  const unit = heightU + gapU
  const racks = targetRacks.value
  if (!racks.length) return 1
  const estimates = racks.map((r) => {
    const total = r.total_u || 1
    const free = r.free_u ?? Math.max(0, total - (r.occupied_u || 0))
    const fromStart = Math.max(0, total - startU + 1)
    const usable = Math.min(free, fromStart)
    if (usable < heightU) return 0
    return Math.floor((usable + gapU) / unit)
  })
  const minFit = Math.min(...estimates)
  return Math.max(0, Number.isFinite(minFit) ? minFit : 0)
})

const occupancyAlertType = computed(() => {
  const s = rackOccupancySummary.value
  if (!targetRacks.value.length) return 'info' as const
  if (s.insufficient.length === targetRacks.value.length) return 'error' as const
  if (s.insufficient.length || suggestedPerRackCount.value < 1) return 'warning' as const
  if (s.occupiedRacks) return 'warning' as const
  return 'info' as const
})

const occupancyAlertTitle = computed(() => {
  const s = rackOccupancySummary.value
  const racks = targetRacks.value
  if (!racks.length) return '请先选择机房以加载机柜占用情况'
  const parts = [
    `目标机柜 ${racks.length} 台`,
    `其中已有设备 ${s.occupiedRacks} 台（已上架合计 ${s.totalDevices} 台）`,
    `合计空闲 ${s.totalFreeU}U`,
    `每柜建议最多 ${suggestedPerRackCount.value} 台`,
  ]
  if (s.insufficient.length) {
    const codes =
      s.insufficient.length <= 4
        ? s.insufficient.join('、')
        : `${s.insufficient.slice(0, 3).join('、')} 等${s.insufficient.length}台`
    parts.push(`空闲不足设备高度：${codes}`)
  }
  return parts.join('；')
})

function isSelectableIp(ip: IpAddress) {
  return (
    !ip.device_id
    && ip.status !== 'disabled'
    && ip.status !== 'allocated'
    && ip.status !== 'reserved'
  )
}

/** @deprecated 兼容旧调用名 */
function isFreeIp(ip: IpAddress) {
  return isSelectableIp(ip)
}

function resolveSelectedIps(ids: string[]) {
  const map = new Map<string, IpAddress>()
  for (const ip of unboundFreeIps.value) map.set(ip.id, ip)
  for (const ip of segmentIps.value) map.set(ip.id, ip)
  return ids.map((id) => map.get(id)).filter((x): x is IpAddress => !!x)
}

function ipToNum(ip: string): number {
  const parts = ip.split('.').map(Number)
  if (parts.length !== 4 || parts.some((n) => Number.isNaN(n))) return Number.MAX_SAFE_INTEGER
  return ((parts[0] << 24) >>> 0) + (parts[1] << 16) + (parts[2] << 8) + parts[3]
}

function padIndex(n: number) {
  return String(n).padStart(2, '0')
}

function buildDeviceRows(): BatchMountNewDevice[] {
  const model = props.models.find((m) => m.id === form.device_model_id)
  const contractName = selectedContractItem.value?.device_name?.trim() || ''
  const rows: BatchMountNewDevice[] = []
  for (let i = 0; i < form.count; i += 1) {
    const idx = form.start_index + i
    const hostname = `${form.name_prefix}${padIndex(idx)}`
    rows.push({
      // 设备名称用合同明细名称，便于采购汇总按品类统计已关联
      name: contractName || hostname,
      hostname,
      serial_number: `${form.serial_prefix}${padIndex(idx)}`,
      device_model_id: form.device_model_id,
      device_type_id: form.device_type_id,
      height_u: form.height_u || model?.height_u || 1,
      contract_id: form.contract_id || null,
    })
  }
  return rows
}

function onBatchContractChange(contractId: string | null) {
  form.contract_id = contractId || null
  form.contract_item_key = ''
  if (!contractId) return
  if (contractItems.value.length === 1) {
    onBatchContractItemChange(contractItemKey(contractItems.value[0]))
  }
}

function onBatchContractItemChange(key: string | null) {
  form.contract_item_key = key || ''
  const item = findContractItem(selectedContract.value, key)
  if (!item) return
  const modelName = (item.device_model_name || '').trim()
  if (!modelName) return
  const mfgName = (item.manufacturer_name || '').trim()
  const hit = props.models.find(
    (m) =>
      m.name === modelName
      && (!mfgName || !m.manufacturer_name || m.manufacturer_name === mfgName),
  )
  if (hit) {
    form.device_model_id = hit.id
    form.height_u = hit.height_u
  }
}

function segmentLabel(s: IpSegment) {
  const app = s.application ? `${s.application} · ` : ''
  const purpose = s.address_purpose ? ` · ${s.address_purpose}` : ''
  return `${app}${s.network}/${s.prefix_len}${purpose}`
}

async function loadIpSegments() {
  segmentLoading.value = true
  try {
    const data = await listIpSegments({ page: 1, page_size: 200 })
    ipSegments.value = data?.items ?? []
  } catch {
    ipSegments.value = []
    ElMessage.error('加载 IP 地址段失败')
  } finally {
    segmentLoading.value = false
  }
}

async function loadFreeIps(force = false) {
  if (!force && freeIpLoadPromise) return freeIpLoadPromise
  if (!force && allFreeIps.value.length) return
  ipLoading.value = true
  freeIpLoadPromise = (async () => {
    try {
      const pages: IpAddress[] = []
      let page = 1
      let total = 0
      do {
        const data = await listIpAddresses({ page, page_size: 200, status: 'free' })
        pages.push(...(data.items || []))
        total = data.pagination?.total ?? pages.length
        page += 1
      } while (pages.length < total && page <= 10)
      allFreeIps.value = pages
    } catch {
      allFreeIps.value = []
      ElMessage.error('加载空闲 IP 失败')
    } finally {
      ipLoading.value = false
      freeIpLoadPromise = null
    }
  })()
  return freeIpLoadPromise
}

async function fetchSegmentFreeIps(segmentId: string): Promise<IpAddress[]> {
  const pages: IpAddress[] = []
  let page = 1
  let total = 0
  do {
    const data = await listIpAddresses({
      page,
      page_size: 200,
      segment_id: segmentId,
      status: 'free',
    })
    pages.push(...(data.items || []))
    total = data.pagination?.total ?? pages.length
    page += 1
  } while (pages.length < total && page <= 20)
  return pages
}

async function openSegment(segment: IpSegment) {
  if (activeSegmentId.value === segment.id && segmentIps.value.length) return

  const seq = ++segmentLoadSeq
  activeSegmentId.value = segment.id

  const cached = segmentIpCache.get(segment.id)
  if (cached) {
    segmentIps.value = cached
    segmentIpsLoading.value = false
    await nextTick()
    syncIpTableSelection()
    // 后台刷新，不挡住交互
    void fetchSegmentFreeIps(segment.id)
      .then((pages) => {
        if (seq !== segmentLoadSeq || activeSegmentId.value !== segment.id) return
        segmentIpCache.set(segment.id, pages)
        segmentIps.value = pages
        void nextTick().then(() => syncIpTableSelection())
      })
      .catch(() => {
        /* 缓存可用，刷新失败可忽略 */
      })
    return
  }

  segmentIpsLoading.value = true
  segmentIps.value = []
  try {
    const pages = await fetchSegmentFreeIps(segment.id)
    if (seq !== segmentLoadSeq || activeSegmentId.value !== segment.id) return
    segmentIpCache.set(segment.id, pages)
    segmentIps.value = pages
  } catch {
    if (seq !== segmentLoadSeq) return
    segmentIps.value = []
    ElMessage.error('加载地址段 IP 失败')
  } finally {
    if (seq === segmentLoadSeq) {
      segmentIpsLoading.value = false
      await nextTick()
      syncIpTableSelection()
    }
  }
}

function setActiveSelection(ids: string[]) {
  const unique = [...new Set(ids)].slice(0, needCount.value)
  activeSelectedIds.value = unique
  void nextTick().then(() => syncIpTableSelection())
}

function ipRowSelectable(row: IpAddress) {
  if (!isFreeIp(row)) return false
  if (otherSelectedIdSet.value.has(row.id)) return false
  if (activeSelectedIdSet.value.has(row.id)) return true
  return activeSelectedIds.value.length < needCount.value
}

function syncIpTableSelection() {
  const table = ipTableRef.value
  if (!table) return
  syncingTableSelection.value = true
  table.clearSelection()
  const selected = activeSelectedIdSet.value
  if (selected.size) {
    for (const row of segmentListIps.value) {
      if (selected.has(row.id)) table.toggleRowSelection(row, true)
    }
  }
  void nextTick(() => {
    syncingTableSelection.value = false
  })
}

function onIpTableSelectionChange(rows: IpAddress[]) {
  if (syncingTableSelection.value) return
  const other = otherSelectedIdSet.value
  let ids = rows.filter((r) => isFreeIp(r) && !other.has(r.id)).map((r) => r.id)
  if (ids.length > needCount.value) {
    ElMessage.warning(`最多选择 ${needCount.value} 条（与新建数量一致）`)
    ids = ids.slice(0, needCount.value)
    setActiveSelection(ids)
    return
  }
  activeSelectedIds.value = ids
}

function ipStatusLabel(row: IpAddress) {
  if (otherSelectedIdSet.value.has(row.id)) {
    return pickKind.value === 'business' ? '已选为BMC' : '已选为业务'
  }
  if (activeSelectedIdSet.value.has(row.id)) {
    return pickKind.value === 'business' ? '已选 · 业务' : '已选 · BMC'
  }
  if (row.status === 'disabled') return '已禁用'
  if (row.status === 'allocated' || row.device_id) {
    return row.device_name ? `已分配 · ${row.device_name}` : '已分配'
  }
  return '空闲'
}

async function loadIpStepData() {
  // 先加载地址段列表，全局空闲 IP 后台拉取（仅范围文本需要），避免挡住点击地址段
  await loadIpSegments()
  void loadFreeIps()
}

async function refreshMountRacks() {
  if (!form.room_id) {
    mountRacks.value = []
    return
  }
  mountRacksLoading.value = true
  try {
    const res = await listRacks({ room_id: form.room_id, page_size: 500 })
    mountRacks.value = res.items || []
  } catch {
    mountRacks.value = props.racks.filter((r) => r.room_id === form.room_id)
    ElMessage.warning('机柜占用信息刷新失败，已使用本地缓存数据')
  } finally {
    mountRacksLoading.value = false
  }
}

function resetForm() {
  step.value = 0
  form.count = 4
  form.name_prefix = 'SRV'
  form.serial_prefix = 'SN'
  form.start_index = 1
  form.device_model_id = ''
  form.device_type_id = props.types[0]?.id || null
  form.height_u = 1
  form.contract_id = null
  form.contract_item_key = ''
  form.room_id = props.rooms[0]?.id || ''
  form.rack_ids = []
  form.start_u = 1
  form.gap_u = 1
  form.per_rack_count = 1
  selectedBusinessIpIds.value = []
  selectedBmcIpIds.value = []
  businessIpRangeText.value = ''
  bmcIpRangeText.value = ''
  businessIpRangeError.value = ''
  bmcIpRangeError.value = ''
  pickKind.value = 'business'
  activeSegmentId.value = null
  segmentIps.value = []
  allFreeIps.value = []
  ipSegments.value = []
  segmentIpCache.clear()
  segmentLoadSeq += 1
  freeIpLoadPromise = null
  previewRows.value = []
  previewLines.value = []
  mountRacks.value = []
}

function syncPerRackCountDefault() {
  form.per_rack_count = Math.max(1, suggestedPerRackCount.value)
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    resetForm()
  },
)

watch(
  () => form.device_model_id,
  (id) => {
    const model = props.models.find((m) => m.id === id)
    if (model) form.height_u = model.height_u
  },
)

watch(
  () => [form.height_u, form.start_u, form.gap_u, form.rack_ids.join(',')] as const,
  () => {
    if (step.value === 2) syncPerRackCountDefault()
  },
)

watch(
  () => form.count,
  () => {
    if (selectedBusinessIpIds.value.length > needCount.value) {
      selectedBusinessIpIds.value = selectedBusinessIpIds.value.slice(0, needCount.value)
    }
    if (selectedBmcIpIds.value.length > needCount.value) {
      selectedBmcIpIds.value = selectedBmcIpIds.value.slice(0, needCount.value)
    }
    void nextTick().then(() => syncIpTableSelection())
  },
)

watch(pickKind, async () => {
  await nextTick()
  syncIpTableSelection()
})

async function onModelChange(value: string | null) {
  if (!value) {
    form.device_model_id = ''
    return
  }
  if (props.models.some((m) => m.id === value)) {
    form.device_model_id = value
    const model = props.models.find((m) => m.id === value)
    if (model) form.height_u = model.height_u
    return
  }
  const name = value.trim()
  if (!name) {
    form.device_model_id = ''
    return
  }
  const existed = props.models.find((m) => m.name === name || m.code === name)
  if (existed) {
    form.device_model_id = existed.id
    form.height_u = existed.height_u
    return
  }
  try {
    let code = name
      .toUpperCase()
      .replace(/[^A-Z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '')
      .slice(0, 40)
    if (!code) code = `MODEL_${Date.now().toString(36).toUpperCase()}`
    if (props.models.some((m) => m.code === code)) {
      code = `${code}_${Date.now().toString(36).toUpperCase()}`.slice(0, 50)
    }
    const created = await createDeviceModel({
      code,
      name,
      height_u: form.height_u || 1,
      power: null,
      description: null,
    })
    emit('model-created', created)
    form.device_model_id = created.id
    form.height_u = created.height_u
    ElMessage.success(`已新建型号「${created.name}」`)
  } catch (error: unknown) {
    form.device_model_id = ''
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '创建型号失败')
  }
}

async function onTypeChange(value: string | null) {
  if (!value) {
    form.device_type_id = null
    return
  }
  if (props.types.some((t) => t.id === value)) {
    form.device_type_id = value
    return
  }
  const name = value.trim()
  if (!name) {
    form.device_type_id = null
    return
  }
  const existed = props.types.find((t) => t.name === name || t.code === name)
  if (existed) {
    form.device_type_id = existed.id
    return
  }
  try {
    let code = name
      .toUpperCase()
      .replace(/[^A-Z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '')
      .slice(0, 40)
    if (!code) code = `TYPE_${Date.now().toString(36).toUpperCase()}`
    if (props.types.some((t) => t.code === code)) {
      code = `${code}_${Date.now().toString(36).toUpperCase()}`.slice(0, 50)
    }
    const created = await createDeviceType({ code, name, description: null })
    emit('type-created', created)
    form.device_type_id = created.id
    ElMessage.success(`已新建设备类型「${created.name}」`)
  } catch (error: unknown) {
    form.device_type_id = null
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '创建设备类型失败')
  }
}

watch(
  () => form.room_id,
  async (roomId) => {
    if (step.value !== 2) {
      form.rack_ids = form.rack_ids.filter((id) => roomRacks.value.some((r) => r.id === id))
      return
    }
    if (!roomId) {
      mountRacks.value = []
      form.rack_ids = []
      return
    }
    form.rack_ids = []
    await refreshMountRacks()
    syncPerRackCountDefault()
  },
)

function parseIpRange(text: string): { startIp: string; endIp: string } | { error: string } {
  const raw = text.trim()
  if (!raw) return { error: '请输入 IP 范围' }
  const rangeMatch = raw.match(/^(.+?)\s*[-~～—–到至]\s*(.+)$/)
  let startIp: string
  let endIp: string
  if (rangeMatch) {
    startIp = rangeMatch[1].trim()
    endIp = rangeMatch[2].trim()
  } else if (/^\d+\.\d+\.\d+\.\d+$/.test(raw)) {
    startIp = raw
    endIp = raw
  } else {
    return { error: '请输入如 192.168.1.10-192.168.1.20 的范围' }
  }
  const startN = ipToNum(startIp)
  const endN = ipToNum(endIp)
  if (startN === Number.MAX_SAFE_INTEGER || endN === Number.MAX_SAFE_INTEGER) {
    return { error: 'IP 格式无效' }
  }
  if (startN > endN) return { error: '起始 IP 不能大于结束 IP' }
  return { startIp, endIp }
}

async function applyIpRange(kind: 'business' | 'bmc') {
  const isBusiness = kind === 'business'
  const text = isBusiness ? businessIpRangeText.value : bmcIpRangeText.value
  const setError = (msg: string) => {
    if (isBusiness) businessIpRangeError.value = msg
    else bmcIpRangeError.value = msg
  }
  setError('')
  if (!text.trim()) {
    if (isBusiness) selectedBusinessIpIds.value = []
    else selectedBmcIpIds.value = []
    void nextTick().then(() => syncIpTableSelection())
    return
  }
  const parsed = parseIpRange(text)
  if ('error' in parsed) {
    setError(parsed.error)
    return
  }
  const startN = ipToNum(parsed.startIp)
  const endN = ipToNum(parsed.endIp)
  const otherIds = new Set(isBusiness ? selectedBmcIpIds.value : selectedBusinessIpIds.value)
  const useSegment = !!(activeSegmentId.value && segmentFreeIps.value.length)
  if (!useSegment) {
    await loadFreeIps()
  }
  const pool = useSegment ? segmentFreeIps.value : unboundFreeIps.value
  const inRange = pool.filter((ip) => {
    const n = ipToNum(ip.system_ip)
    return n >= startN && n <= endN && !otherIds.has(ip.id)
  })
  if (!inRange.length) {
    setError(
      useSegment
        ? '当前地址段范围内没有可勾选的空闲 IP'
        : '该范围内没有可用空闲地址',
    )
    return
  }
  if (inRange.length < needCount.value) {
    setError(
      `范围内仅 ${inRange.length} 条空闲，不足新建数量 ${needCount.value}，请扩大范围或减少新建数量`,
    )
    return
  }
  const ids = inRange.slice(0, needCount.value).map((ip) => ip.id)
  if (isBusiness) selectedBusinessIpIds.value = ids
  else selectedBmcIpIds.value = ids
  pickKind.value = kind
  void nextTick().then(() => syncIpTableSelection())
  ElMessage.success(
    `已选中 ${ids.length} 条${isBusiness ? '业务IP' : 'BMC地址'}（与新建数量一致）`,
  )
}

function clearIpRange(kind: 'business' | 'bmc') {
  if (kind === 'business') {
    businessIpRangeText.value = ''
    businessIpRangeError.value = ''
    selectedBusinessIpIds.value = []
  } else {
    bmcIpRangeText.value = ''
    bmcIpRangeError.value = ''
    selectedBmcIpIds.value = []
  }
  void nextTick().then(() => syncIpTableSelection())
}

function buildPreview() {
  previewRows.value = buildDeviceRows()
  const targets = targetRacks.value
  const roomName = props.rooms.find((r) => r.id === form.room_id)?.name || ''
  const biz = selectedBusinessIps.value
  const bmc = selectedBmcIps.value
  const contractNo = selectedContract.value?.contract_no || '未关联'
  const contractDevice = selectedContractItem.value?.device_name || '—'
  previewLines.value = [
    `机房：${roomName}`,
    `采购合同：${contractNo}`,
    `合同设备：${contractDevice}`,
    `新建设备：${previewRows.value.length} 台（主机名 ${form.name_prefix}${padIndex(form.start_index)} … ${form.name_prefix}${padIndex(form.start_index + form.count - 1)}）`,
    `业务IP：${biz.length} 条${biz.length ? `（${biz[0].system_ip} … ${biz.at(-1)?.system_ip}）` : '（跳过）'}`,
    `BMC地址：${bmc.length} 条${bmc.length ? `（${bmc[0].system_ip} … ${bmc.at(-1)?.system_ip}）` : '（跳过）'}`,
    `目标机柜：${targets.length} 台（已有设备 ${rackOccupancySummary.value.occupiedRacks} 台 / 已上架 ${rackOccupancySummary.value.totalDevices} 台 / 空闲 ${rackOccupancySummary.value.totalFreeU}U）`,
    `起始 U：${form.start_u}，设备间隔：${form.gap_u}U，每柜最多：${form.per_rack_count} 台（按空闲U建议 ${suggestedPerRackCount.value}）`,
  ]
}

async function nextStep() {
  if (step.value === 0) {
    if (!form.device_model_id) {
      ElMessage.warning('请输入或选择设备型号')
      return
    }
    if (form.count < 1) {
      ElMessage.warning('新建数量至少为 1')
      return
    }
    if (!form.name_prefix.trim() || !form.serial_prefix.trim()) {
      ElMessage.warning('请填写主机名前缀与序列号前缀')
      return
    }
    if (form.contract_id && !form.contract_item_key) {
      ElMessage.warning('请选择合同内的设备名称，以便采购汇总正确统计已关联数量')
      return
    }
    step.value = 1
    await loadIpStepData()
    return
  }
  if (step.value === 1) {
    if (
      selectedBusinessIpIds.value.length
      && selectedBusinessIpIds.value.length !== needCount.value
    ) {
      ElMessage.warning(
        `业务IP 已选 ${selectedBusinessIpIds.value.length} 条，须等于新建数量 ${needCount.value}`,
      )
      return
    }
    if (selectedBmcIpIds.value.length && selectedBmcIpIds.value.length !== needCount.value) {
      ElMessage.warning(
        `BMC地址 已选 ${selectedBmcIpIds.value.length} 条，须等于新建数量 ${needCount.value}`,
      )
      return
    }
    step.value = 2
    await refreshMountRacks()
    await nextTick()
    syncPerRackCountDefault()
    return
  }
  if (step.value === 2) {
    if (!form.room_id) {
      ElMessage.warning('请选择机房')
      return
    }
    if (!roomRacks.value.length) {
      ElMessage.warning('该机房暂无机柜')
      return
    }
    if (!targetRacks.value.length) {
      ElMessage.warning('请选择目标机柜')
      return
    }
    const summary = rackOccupancySummary.value
    if (summary.insufficient.length === targetRacks.value.length) {
      ElMessage.warning('所选机柜空闲 U 均不足以放下当前设备高度，请更换机柜或降低设备 U 数')
      return
    }
    if (suggestedPerRackCount.value < 1) {
      ElMessage.warning('按当前起始 U / 空闲容量，目标机柜无法再上架，请调整机柜范围或起始 U')
      return
    }
    const capacity = targetRacks.value.length * Math.max(1, form.per_rack_count)
    if (needCount.value > capacity) {
      ElMessage.warning(
        `新建 ${needCount.value} 台超过目标容量（${targetRacks.value.length} 柜 × 每柜 ${form.per_rack_count} = ${capacity}），请增加机柜或提高每柜数量`,
      )
      return
    }
    if (summary.insufficient.length) {
      ElMessage.warning(
        `部分机柜空闲不足（${summary.insufficient.slice(0, 4).join('、')}${summary.insufficient.length > 4 ? '…' : ''}），上架时将自动跳过无法容纳的机柜`,
      )
    }
    buildPreview()
  }
  step.value += 1
}

async function submit() {
  submitting.value = true
  try {
    const newDevices = buildDeviceRows()
    const result = await batchMountDevices({
      room_id: form.room_id,
      new_devices: newDevices,
      rack_ids: form.rack_ids,
      per_rack_count: form.per_rack_count,
      start_u: form.start_u,
      gap_u: form.gap_u,
      ip_ids: selectedBusinessIpIds.value,
      bmc_ip_ids: selectedBmcIpIds.value,
    })
    ElMessage.success(
      `新建 ${result.created} 台，上架 ${result.mounted} 台，关联 IP ${result.ip_bound ?? 0} 条，跳过 ${result.skipped} 台`,
    )
    if (result.errors?.length) {
      ElMessage.warning(result.errors.slice(0, 6).join('; '))
    }
    visible.value = false
    emit('success')
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '批量新建失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="批量新建设备"
    width="920px"
    destroy-on-close
    top="3vh"
  >
    <el-steps :active="step" finish-status="success" align-center style="margin-bottom: 20px">
      <el-step title="设备信息" />
      <el-step title="IP 地址" />
      <el-step title="机柜上架" />
      <el-step title="确认提交" />
    </el-steps>

    <div v-if="step === 0">
      <el-form label-width="110px">
        <el-form-item label="采购合同">
          <el-select
            v-model="form.contract_id"
            clearable
            filterable
            style="width: 100%"
            placeholder="选择采购合同（可选）"
            @change="onBatchContractChange"
          >
            <el-option
              v-for="c in contracts || []"
              :key="c.id"
              :label="c.project_no ? `${c.contract_no} · ${c.project_no}` : c.contract_no"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="合同设备">
          <el-select
            v-model="form.contract_item_key"
            clearable
            filterable
            style="width: 100%"
            placeholder="选择合同内的设备名称"
            :disabled="!form.contract_id"
            @change="onBatchContractItemChange"
          >
            <el-option
              v-for="it in contractItems"
              :key="contractItemKey(it)"
              :label="it.device_name"
              :value="contractItemKey(it)"
            />
          </el-select>
          <span v-if="selectedContractItem" class="field-tip">
            设备名称将设为「{{ selectedContractItem.device_name }}」，计入采购汇总已关联
          </span>
        </el-form-item>
        <el-form-item label="新建数量" required>
          <el-input-number v-model="form.count" :min="1" :max="200" />
        </el-form-item>
        <el-form-item label="起始序号">
          <el-input-number v-model="form.start_index" :min="1" :max="9999" />
        </el-form-item>
        <el-form-item label="主机名前缀" required>
          <el-input v-model="form.name_prefix" placeholder="如 SRV → 主机名 SRV01" />
        </el-form-item>
        <el-form-item label="序列号前缀" required>
          <el-input v-model="form.serial_prefix" placeholder="如 SN → SN01" />
        </el-form-item>
        <el-form-item label="设备型号" required>
          <el-select
            v-model="form.device_model_id"
            filterable
            allow-create
            default-first-option
            placeholder="输入自定义型号或选择已有"
            style="width: 100%"
            @change="onModelChange"
          >
            <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备类型">
          <el-select
            v-model="form.device_type_id"
            clearable
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入自定义类型"
            style="width: 100%"
            @change="onTypeChange"
          >
            <el-option v-for="t in types" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="高度 (U)">
          <el-input-number v-model="form.height_u" :min="1" :max="10" />
        </el-form-item>
      </el-form>
      <el-alert
        type="info"
        :closable="false"
        :title="`预览：主机名 ${form.name_prefix}${padIndex(form.start_index)} … ${form.name_prefix}${padIndex(form.start_index + form.count - 1)}${selectedContractItem ? ` · 设备名称「${selectedContractItem.device_name}」` : ''}`"
      />
    </div>

    <div v-else-if="step === 1">
      <el-form label-width="110px" style="margin-bottom: 8px" v-loading="ipLoading">
        <el-form-item label="业务IP范围">
          <div class="ip-range-row">
            <el-input
              v-model="businessIpRangeText"
              clearable
              placeholder="手动输入，如 192.168.1.10-192.168.1.13"
              @keyup.enter="applyIpRange('business')"
            />
            <el-button type="primary" plain @click="applyIpRange('business')">应用</el-button>
            <el-button link @click="clearIpRange('business')">清空</el-button>
          </div>
        </el-form-item>
        <p v-if="businessIpRangeError" class="range-error">{{ businessIpRangeError }}</p>
        <el-form-item label="BMC地址范围">
          <div class="ip-range-row">
            <el-input
              v-model="bmcIpRangeText"
              clearable
              placeholder="手动输入，如 10.0.0.10-10.0.0.13"
              @keyup.enter="applyIpRange('bmc')"
            />
            <el-button type="primary" plain @click="applyIpRange('bmc')">应用</el-button>
            <el-button link @click="clearIpRange('bmc')">清空</el-button>
          </div>
        </el-form-item>
        <p v-if="bmcIpRangeError" class="range-error">{{ bmcIpRangeError }}</p>
      </el-form>

      <div class="pick-toolbar">
        <span class="hint" style="margin: 0">{{ selectedIpSummary }}</span>
        <el-radio-group v-model="pickKind" size="small">
          <el-radio-button value="business">勾选业务IP</el-radio-button>
          <el-radio-button value="bmc">勾选BMC地址</el-radio-button>
        </el-radio-group>
      </div>
      <p class="hint">
        点击左侧地址段后仅加载空闲 IP 供勾选；选中数量须等于新建数量（{{ needCount }}）。
      </p>

      <div class="ip-pick-layout">
        <div class="segment-panel" v-loading="segmentLoading">
          <div class="panel-title">IP 地址段</div>
          <el-empty v-if="!ipSegments.length && !segmentLoading" description="暂无地址段" :image-size="56" />
          <button
            v-for="s in ipSegments"
            :key="s.id"
            type="button"
            class="segment-item"
            :class="{ active: activeSegmentId === s.id }"
            @click="openSegment(s)"
          >
            <div class="seg-name">{{ segmentLabel(s) }}</div>
            <div class="seg-meta">
              空闲 {{ s.free_count }} / 共 {{ s.total_count }}
            </div>
          </button>
        </div>

        <div class="ip-panel" v-loading="segmentIpsLoading">
          <div class="panel-title">
            <template v-if="activeSegment">
              {{ segmentLabel(activeSegment) }} · 空闲 {{ segmentListIps.length }} 条
              · 当前勾选
              {{ pickKind === 'business' ? '业务' : 'BMC' }}
              {{ activeSelectedIds.length }}/{{ needCount }}
            </template>
            <template v-else>请先选择左侧地址段</template>
          </div>
          <el-empty
            v-if="activeSegmentId && !segmentListIps.length && !segmentIpsLoading"
            description="该段暂无空闲地址"
            :image-size="56"
          />
          <el-table
            v-else-if="segmentListIps.length"
            ref="ipTableRef"
            :data="segmentListIps"
            size="small"
            height="300"
            row-key="id"
            @selection-change="onIpTableSelectionChange"
          >
            <el-table-column
              type="selection"
              width="48"
              :selectable="ipRowSelectable"
            />
            <el-table-column prop="system_ip" label="IP 地址" min-width="130" />
            <el-table-column label="状态" min-width="140">
              <template #default="{ row }">
                <span :class="{ 'text-muted': otherSelectedIdSet.has(row.id) }">
                  {{ ipStatusLabel(row) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="label" label="标签" min-width="90">
              <template #default="{ row }">{{ row.label || '—' }}</template>
            </el-table-column>
          </el-table>
          <el-empty
            v-else-if="!activeSegmentId"
            description="点击左侧地址段开始选择"
            :image-size="64"
          />
        </div>
      </div>
    </div>

    <div v-else-if="step === 2" v-loading="mountRacksLoading">
      <el-form label-width="110px">
        <el-form-item label="机房" required>
          <el-select v-model="form.room_id" filterable style="width: 100%">
            <el-option v-for="r in rooms" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="机柜范围">
          <RackRangePicker v-model="form.rack_ids" :racks="roomRacks" empty-means-all />
        </el-form-item>
        <el-form-item label="起始 U 位" required>
          <el-input-number v-model="form.start_u" :min="1" :max="100" />
        </el-form-item>
        <el-form-item label="设备间隔">
          <el-input-number v-model="form.gap_u" :min="0" :max="10" />
          <span class="field-tip">U（默认 1，设备之间空 1U）</span>
        </el-form-item>
        <el-form-item label="每柜最多">
          <el-input-number v-model="form.per_rack_count" :min="1" :max="200" />
          <span class="field-tip">
            按空闲U/起始U估算 = {{ suggestedPerRackCount }}
            <el-button link type="primary" @click="syncPerRackCountDefault">按计算填入</el-button>
          </span>
        </el-form-item>
      </el-form>
      <el-alert
        :type="occupancyAlertType"
        :closable="false"
        :title="occupancyAlertTitle"
        description="橙色机柜表示已有设备；上架时会跳过已被占用的 U 位，按机柜编号顺序自动寻找可用位置。"
        show-icon
        style="margin-top: 8px"
      />
    </div>

    <div v-else>
      <ul class="preview-list">
        <li v-for="(line, i) in previewLines" :key="i">{{ line }}</li>
      </ul>
      <el-table v-if="previewRows.length" :data="previewRows.slice(0, 8)" size="small" style="margin-top: 12px">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="serial_number" label="序列号" />
        <el-table-column label="业务IP">
          <template #default="{ $index }">
            {{ selectedBusinessIps[$index]?.system_ip || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="BMC地址">
          <template #default="{ $index }">
            {{ selectedBmcIps[$index]?.system_ip || '—' }}
          </template>
        </el-table-column>
      </el-table>
      <p v-if="previewRows.length > 8" class="hint">… 共 {{ previewRows.length }} 台</p>
    </div>

    <template #footer>
      <el-button v-if="step > 0" @click="step -= 1">上一步</el-button>
      <el-button v-if="step < 3" type="primary" @click="nextStep">下一步</el-button>
      <el-button v-else type="primary" :loading="submitting" @click="submit">确认新建并上架</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.ip-range-row {
  display: flex;
  gap: 8px;
  width: 100%;
  align-items: center;
}
.ip-range-row .el-input {
  flex: 1;
}
.range-error {
  margin: -8px 0 8px 110px;
  color: var(--el-color-danger);
  font-size: 12px;
}
.hint {
  margin: 0 0 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
}
.pick-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.ip-pick-layout {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 12px;
  min-height: 320px;
}
.segment-panel,
.ip-panel {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 10px;
  background: var(--el-fill-color-blank);
  overflow: auto;
  max-height: 360px;
}
.panel-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 10px;
  color: var(--el-text-color-primary);
}
.segment-item {
  display: block;
  width: 100%;
  text-align: left;
  border: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.segment-item:hover {
  border-color: var(--el-color-primary-light-5);
}
.segment-item.active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}
.seg-name {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
}
.seg-meta {
  margin-top: 4px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.text-muted {
  color: var(--el-text-color-secondary);
}
.field-tip {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.preview-list {
  margin: 0;
  padding-left: 18px;
  line-height: 1.8;
}
@media (max-width: 800px) {
  .ip-pick-layout {
    grid-template-columns: 1fr;
  }
}
</style>
