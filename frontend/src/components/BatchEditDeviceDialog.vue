<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  batchUpdateDevices,
  createDeviceModel,
  createManufacturer,
  type Device,
  type DeviceBatchUpdatePayload,
  type DeviceModel,
  type DeviceType,
  type Manufacturer,
} from '@/api/device'
import { listIpAddresses, listIpSegments, type IpAddress, type IpSegment } from '@/api/ip'
import type { Rack } from '@/api/rack'
import type { Room } from '@/api/room'
import {
  contractItemKey,
  findContractItem,
  syncContractModelsById,
  type DeviceContract,
  type DeviceContractItem,
} from '@/api/contract'

export type BatchEditMode =
  | 'contract'
  | 'type'
  | 'model'
  | 'manufacturer'
  | 'unmount'
  | 'mount'
  | 'ip'

const MODE_TITLE: Record<BatchEditMode, string> = {
  contract: '合同 / 合同设备',
  type: '类型',
  model: '型号',
  manufacturer: '产品厂商',
  unmount: '批量下架',
  mount: '移动设备',
  ip: '改 IP',
}

const props = defineProps<{
  modelValue: boolean
  /** 当前批量修改项（由下拉菜单传入） */
  mode: BatchEditMode
  devices: Device[]
  rooms: Room[]
  racks: Rack[]
  models: DeviceModel[]
  types: DeviceType[]
  manufacturers: Manufacturer[]
  contracts: DeviceContract[]
}>()

const emit = defineEmits<{
  'update:modelValue': [boolean]
  success: []
  'model-created': [DeviceModel]
  'manufacturer-created': [Manufacturer]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const dialogTitle = computed(() => `批量修改 · ${MODE_TITLE[props.mode]}`)
const dialogWidth = computed(() =>
  props.mode === 'ip' ? '860px' : props.mode === 'mount' || props.mode === 'contract' ? '640px' : '480px',
)

const submitting = ref(false)
const localManufacturers = ref<Manufacturer[]>([])
const localModels = ref<DeviceModel[]>([])

/** —— 改 IP：先选地址段，再勾选空闲 IP —— */
const segmentLoading = ref(false)
const segmentIpsLoading = ref(false)
const ipSegments = ref<IpSegment[]>([])
const activeSegmentId = ref<string | null>(null)
const segmentIps = ref<IpAddress[]>([])
const segmentIpCache = new Map<string, IpAddress[]>()
let segmentLoadSeq = 0
const pickKind = ref<'business' | 'bmc'>('business')
const selectedBusinessIpIds = ref<string[]>([])
const selectedBmcIpIds = ref<string[]>([])
const selectedVipIpId = ref<string | null>(null)
const ipTableRef = ref<{
  clearSelection: () => void
  toggleRowSelection: (row: IpAddress, selected?: boolean) => void
} | null>(null)
const syncingTableSelection = ref(false)

const needCount = computed(() => Math.max(0, props.devices.length))
const segmentFreeIps = computed(() =>
  segmentIps.value.filter((ip) => ip.status === 'free' && !ip.device_id),
)
const activeSegment = computed(
  () => ipSegments.value.find((s) => s.id === activeSegmentId.value) || null,
)
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
const activeSelectedIdSet = computed(() => new Set(activeSelectedIds.value))
const otherSelectedIdSet = computed(() => new Set(otherSelectedIds.value))
const selectedIpSummary = computed(() => {
  const n = needCount.value
  const biz = selectedBusinessIpIds.value.length
  const bmc = selectedBmcIpIds.value.length
  return `业务 IP ${biz}/${n} · BMC ${bmc}/${n}（按选中 ${n} 台设备配对）`
})

watch(
  () => props.manufacturers,
  (list) => {
    localManufacturers.value = [...(list || [])]
  },
  { immediate: true },
)
watch(
  () => props.models,
  (list) => {
    localModels.value = [...(list || [])]
  },
  { immediate: true },
)

const apply = reactive({
  contract: false,
  linkedModelMfg: true,
  type: false,
  model: false,
  manufacturer: false,
  unmount: false,
  mount: false,
  ip: false,
  clearBusinessIp: false,
  clearBmcIp: false,
  clearVip: false,
})

const form = reactive({
  contract_id: '' as string | null,
  contract_item_key: '',
  device_type_id: '' as string | null,
  device_model_id: '',
  manufacturer_id: null as string | null,
  room_id: '',
  rack_id: '',
  start_u: 1,
  gap_u: 0,
})

const selectedCount = computed(() => props.devices.length)

const selectedContract = computed(
  () => props.contracts.find((c) => c.id === form.contract_id) || null,
)

const contractItems = computed((): DeviceContractItem[] => {
  const items = selectedContract.value?.device_items
  return Array.isArray(items)
    ? items.filter((it) => {
        if (!it.device_name) return false
        const kind = it.item_kind || 'hardware'
        return kind !== 'software'
      })
    : []
})

const roomRacks = computed(() =>
  form.room_id ? props.racks.filter((r) => r.room_id === form.room_id) : props.racks,
)

function contractItemOptionLabel(it: DeviceContractItem) {
  const name = (it.device_name || '').trim()
  const model = (it.device_model_name || '').trim()
  const mfg = (it.manufacturer_name || '').trim()
  if (model && mfg) return `${name} · ${model} · ${mfg}`
  if (model) return `${name} · ${model}`
  return name
}

function findModelForContract(modelName: string, mfg: Manufacturer | null) {
  const name = modelName.trim()
  if (!name) return undefined
  const lower = name.toLowerCase()
  const byName = localModels.value.filter(
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

function genManufacturerCode(name: string) {
  const base = name
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 20)
  return base || `MFG_${Date.now().toString(36).toUpperCase()}`
}

async function ensureManufacturer(name: string | null | undefined): Promise<Manufacturer | null> {
  const trimmed = (name || '').trim()
  if (!trimmed) return null
  const hit = localManufacturers.value.find((m) => m.name === trimmed || m.code === trimmed)
  if (hit) return hit
  let code = genManufacturerCode(trimmed)
  if (localManufacturers.value.some((m) => m.code === code)) {
    code = `${code}_${Date.now().toString(36).toUpperCase()}`.slice(0, 50)
  }
  const created = await createManufacturer({
    code,
    name: trimmed,
    description: '来自合同信息同步',
  })
  localManufacturers.value = [...localManufacturers.value, created].sort((a, b) =>
    a.name.localeCompare(b.name),
  )
  emit('manufacturer-created', created)
  return created
}

async function onContractChange(contractId: string | null) {
  form.contract_id = contractId || null
  form.contract_item_key = ''
  if (!contractId) return
  try {
    await syncContractModelsById(contractId)
  } catch {
    /* ignore */
  }
  if (contractItems.value.length === 1) {
    await onContractItemChange(contractItemKey(contractItems.value[0]))
  }
}

async function onContractItemChange(key: string | null) {
  form.contract_item_key = key || ''
  const item = findContractItem(selectedContract.value, key)
  if (!item || !apply.linkedModelMfg) return
  try {
    const mfg = await ensureManufacturer(item.manufacturer_name)
    form.manufacturer_id = mfg?.id || null
    apply.manufacturer = true
    const modelName = (item.device_model_name || item.device_name || '').trim()
    if (!modelName) return
    let hit = findModelForContract(modelName, mfg)
    if (!hit) {
      let code = modelName
        .toUpperCase()
        .replace(/[^A-Z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '')
        .slice(0, 50)
      if (!code) code = `MDL_${Date.now().toString(36).toUpperCase()}`
      if (localModels.value.some((m) => m.code === code)) {
        code = `${code}_${Date.now().toString(36).toUpperCase()}`.slice(0, 50)
      }
      hit = await createDeviceModel({
        code,
        name: modelName,
        height_u: 1,
        manufacturer_id: mfg?.id || null,
        description: '来自合同信息同步',
      })
      localModels.value = [...localModels.value, hit]
      emit('model-created', hit)
    }
    form.device_model_id = hit.id
    apply.model = true
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '匹配合同厂商/型号失败')
  }
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

function segmentLabel(s: IpSegment) {
  const app = s.application ? `${s.application} · ` : ''
  const purpose = s.address_purpose ? ` · ${s.address_purpose}` : ''
  return `${app}${s.network}/${s.prefix_len}${purpose}`
}

function isFreeIp(ip: IpAddress) {
  return ip.status === 'free' && !ip.device_id
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
    pages.push(...((data.items || []) as IpAddress[]).filter(isFreeIp))
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
    void fetchSegmentFreeIps(segment.id)
      .then((pages) => {
        if (seq !== segmentLoadSeq || activeSegmentId.value !== segment.id) return
        segmentIpCache.set(segment.id, pages)
        segmentIps.value = pages
        void nextTick().then(() => syncIpTableSelection())
      })
      .catch(() => {
        /* ignore */
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
    ElMessage.error('加载地址段空闲 IP 失败')
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
  if (selectedVipIpId.value === row.id) return false
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
    for (const row of segmentFreeIps.value) {
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
  const vip = selectedVipIpId.value
  let ids = rows
    .filter((r) => isFreeIp(r) && !other.has(r.id) && r.id !== vip)
    .map((r) => r.id)
  if (ids.length > needCount.value) {
    ElMessage.warning(`最多选择 ${needCount.value} 条（与选中设备数一致）`)
    ids = ids.slice(0, needCount.value)
    setActiveSelection(ids)
    return
  }
  activeSelectedIds.value = ids
}

function ipStatusLabel(row: IpAddress) {
  if (otherSelectedIdSet.value.has(row.id)) {
    return pickKind.value === 'business' ? '已选为 BMC' : '已选为业务'
  }
  if (selectedVipIpId.value === row.id) return '已选为 VIP'
  if (activeSelectedIdSet.value.has(row.id)) {
    return pickKind.value === 'business' ? '已选 · 业务' : '已选 · BMC'
  }
  return '空闲'
}

function resetIpPicker() {
  pickKind.value = 'business'
  selectedBusinessIpIds.value = []
  selectedBmcIpIds.value = []
  selectedVipIpId.value = null
  activeSegmentId.value = null
  segmentIps.value = []
  segmentIpCache.clear()
  segmentLoadSeq += 1
}

async function loadIpStepData() {
  resetIpPicker()
  await loadIpSegments()
}

function resetForm() {
  Object.assign(apply, {
    contract: false,
    linkedModelMfg: true,
    type: false,
    model: false,
    manufacturer: false,
    unmount: false,
    mount: false,
    ip: false,
    clearBusinessIp: false,
    clearBmcIp: false,
    clearVip: false,
  })
  if (props.mode in apply) {
    ;(apply as Record<string, boolean>)[props.mode] = true
  }
  Object.assign(form, {
    contract_id: null,
    contract_item_key: '',
    device_type_id: null,
    device_model_id: '',
    manufacturer_id: null,
    room_id: props.rooms[0]?.id || '',
    rack_id: '',
    start_u: 1,
    gap_u: 0,
  })
  resetIpPicker()
}

watch(visible, async (v) => {
  if (!v) return
  resetForm()
  const roomId = props.devices.find((d) => d.room_id)?.room_id || props.rooms[0]?.id || ''
  form.room_id = roomId
  const rackList = roomId ? props.racks.filter((r) => r.room_id === roomId) : props.racks
  form.rack_id = props.devices.find((d) => d.rack_id)?.rack_id || rackList[0]?.id || ''
  if (props.mode === 'ip') void loadIpStepData()
})

watch(pickKind, async () => {
  await nextTick()
  syncIpTableSelection()
})

watch(
  () => apply.clearBusinessIp,
  (on) => {
    if (on) {
      selectedBusinessIpIds.value = []
      if (pickKind.value === 'business') pickKind.value = 'bmc'
      void nextTick().then(() => syncIpTableSelection())
    }
  },
)
watch(
  () => apply.clearBmcIp,
  (on) => {
    if (on) {
      selectedBmcIpIds.value = []
      if (pickKind.value === 'bmc') pickKind.value = 'business'
      void nextTick().then(() => syncIpTableSelection())
    }
  },
)
watch(
  () => apply.clearVip,
  (on) => {
    if (on) selectedVipIpId.value = null
  },
)

watch(
  () => form.room_id,
  () => {
    if (!roomRacks.value.find((r) => r.id === form.rack_id)) {
      form.rack_id = roomRacks.value[0]?.id || ''
    }
  },
)

function validate(): string | null {
  if (!selectedCount.value) return '请先选择设备'
  if (apply.contract) {
    if (!form.contract_id) return '请选择采购合同'
    if (!form.contract_item_key) return '请选择合同内的设备名称'
  }
  if (apply.type && !form.device_type_id) return '请选择设备类型'
  if (apply.model && !form.device_model_id) return '请选择产品型号'
  if (apply.mount) {
    if (!form.rack_id) return '请选择目标机柜'
    if (!form.start_u || form.start_u < 1) return '请填写起始 U'
  }
  if (apply.ip) {
    const n = selectedCount.value
    if (!apply.clearBusinessIp && selectedBusinessIpIds.value.length) {
      if (selectedBusinessIpIds.value.length !== n) {
        return `业务 IP 已选 ${selectedBusinessIpIds.value.length} 条，须等于设备数 ${n}`
      }
    }
    if (!apply.clearBmcIp && selectedBmcIpIds.value.length) {
      if (selectedBmcIpIds.value.length !== n) {
        return `BMC IP 已选 ${selectedBmcIpIds.value.length} 条，须等于设备数 ${n}`
      }
    }
    const ipAny =
      apply.clearBusinessIp ||
      apply.clearBmcIp ||
      apply.clearVip ||
      selectedBusinessIpIds.value.length > 0 ||
      selectedBmcIpIds.value.length > 0 ||
      !!selectedVipIpId.value
    if (!ipAny) return '请先选择地址段并勾选空闲 IP，或勾选清空'
  }
  return null
}

async function submit() {
  const err = validate()
  if (err) {
    ElMessage.warning(err)
    return
  }

  const payload: DeviceBatchUpdatePayload = {
    ids: props.devices.map((d) => d.id),
  }
  const fields: NonNullable<DeviceBatchUpdatePayload['fields']> = {}

  if (apply.contract) {
    const item = findContractItem(selectedContract.value, form.contract_item_key)
    fields.contract_id = form.contract_id || ''
    fields.name = item?.device_name || undefined
  }
  if (apply.type) fields.device_type_id = form.device_type_id || ''
  if (apply.model) fields.device_model_id = form.device_model_id
  if (apply.manufacturer) fields.manufacturer_id = form.manufacturer_id || ''

  if (Object.keys(fields).length) payload.fields = fields

  if (apply.unmount) payload.unmount = true
  if (apply.mount) {
    payload.mount = {
      rack_id: form.rack_id,
      start_u: form.start_u,
      gap_u: form.gap_u,
    }
  }
  if (apply.ip) {
    if (apply.clearBusinessIp) {
      payload.fields = { ...(payload.fields || {}), system_ip_id: '' }
    } else if (selectedBusinessIpIds.value.length) {
      payload.system_ip_ids = [...selectedBusinessIpIds.value]
    }
    if (apply.clearBmcIp) {
      payload.fields = { ...(payload.fields || {}), bmc_ip_id: '' }
    } else if (selectedBmcIpIds.value.length) {
      payload.bmc_ip_ids = [...selectedBmcIpIds.value]
    }
    if (apply.clearVip) {
      payload.vip_ip_id = ''
    } else if (selectedVipIpId.value) {
      payload.vip_ip_id = selectedVipIpId.value
    }
  }

  submitting.value = true
  try {
    const result = await batchUpdateDevices(payload)
    const parts = [
      result.updated ? `更新 ${result.updated}` : '',
      result.unmounted ? `下架 ${result.unmounted}` : '',
      result.mounted ? `上架 ${result.mounted}` : '',
      result.skipped ? `跳过 ${result.skipped}` : '',
    ].filter(Boolean)
    ElMessage.success(parts.join('，') || '已完成')
    if (result.errors.length) {
      ElMessage.warning(result.errors.slice(0, 5).join('；'))
    }
    visible.value = false
    emit('success')
  } catch (error: unknown) {
    const e = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(e.response?.data?.message || e.message || '批量修改失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    :width="dialogWidth"
    destroy-on-close
    class="batch-edit-dialog"
  >
    <p class="hint">已选 {{ selectedCount }} 台设备</p>

    <div v-if="mode === 'contract'" class="panel">
      <el-form label-width="100px" @submit.prevent>
        <el-form-item label="采购合同" required>
          <el-select
            v-model="form.contract_id"
            filterable
            clearable
            placeholder="选择合同"
            style="width: 100%"
            @change="onContractChange"
          >
            <el-option
              v-for="c in contracts"
              :key="c.id"
              :label="c.contract_no"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="合同设备" required>
          <el-select
            v-model="form.contract_item_key"
            filterable
            clearable
            placeholder="选择合同内的设备名称"
            style="width: 100%"
            :disabled="!form.contract_id"
            @change="onContractItemChange"
          >
            <el-option
              v-for="it in contractItems"
              :key="contractItemKey(it)"
              :label="contractItemOptionLabel(it)"
              :value="contractItemKey(it)"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="apply.linkedModelMfg">选合同设备时一并匹配产品型号与产品厂商</el-checkbox>
        </el-form-item>
      </el-form>
    </div>

    <div v-else-if="mode === 'type'" class="panel">
      <el-select v-model="form.device_type_id" filterable clearable placeholder="设备类型" style="width: 100%">
        <el-option v-for="t in types" :key="t.id" :label="t.name" :value="t.id" />
      </el-select>
    </div>

    <div v-else-if="mode === 'model'" class="panel">
      <el-select v-model="form.device_model_id" filterable clearable placeholder="产品型号" style="width: 100%">
        <el-option v-for="m in localModels" :key="m.id" :label="m.name" :value="m.id" />
      </el-select>
    </div>

    <div v-else-if="mode === 'manufacturer'" class="panel">
      <el-select
        v-model="form.manufacturer_id"
        filterable
        clearable
        placeholder="产品厂商（清空则回退产品型号厂商）"
        style="width: 100%"
      >
        <el-option v-for="m in localManufacturers" :key="m.id" :label="m.name" :value="m.id" />
      </el-select>
    </div>

    <div v-else-if="mode === 'unmount'" class="panel">
      <p class="sub-hint warn flush">下架将释放设备已分配的 IP，设备回到库存状态。</p>
    </div>

    <div v-else-if="mode === 'mount'" class="panel">
      <el-form label-width="90px" @submit.prevent>
        <el-form-item label="机房">
          <el-select v-model="form.room_id" filterable placeholder="机房" style="width: 100%">
            <el-option v-for="r in rooms" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="机柜" required>
          <el-select v-model="form.rack_id" filterable placeholder="机柜" style="width: 100%">
            <el-option v-for="r in roomRacks" :key="r.id" :label="r.code" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="起始 U">
          <el-input-number v-model="form.start_u" :min="1" :max="100" />
        </el-form-item>
        <el-form-item label="间隔 U">
          <el-input-number v-model="form.gap_u" :min="0" :max="50" />
        </el-form-item>
      </el-form>
    </div>

    <div v-else-if="mode === 'ip'" class="panel ip-mode">
      <p class="hint">
        已选 {{ needCount }} 台设备。请先选左侧地址段，再勾选空闲 IP（被占用地址不显示）。
        业务 / BMC 各需选满 {{ needCount }} 条，或勾选清空。
      </p>
      <div class="pick-toolbar">
        <span class="summary">{{ selectedIpSummary }}</span>
        <el-radio-group v-model="pickKind" size="small" :disabled="apply.clearBusinessIp && apply.clearBmcIp">
          <el-radio-button value="business" :disabled="apply.clearBusinessIp">勾选业务 IP</el-radio-button>
          <el-radio-button value="bmc" :disabled="apply.clearBmcIp">勾选 BMC</el-radio-button>
        </el-radio-group>
      </div>
      <div class="clear-row">
        <el-checkbox v-model="apply.clearBusinessIp">清空业务 IP</el-checkbox>
        <el-checkbox v-model="apply.clearBmcIp">清空 BMC IP</el-checkbox>
        <el-checkbox v-model="apply.clearVip">清空 VIP</el-checkbox>
      </div>

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
            <div class="seg-meta">空闲 {{ s.free_count }} / 共 {{ s.total_count }}</div>
          </button>
        </div>

        <div class="ip-panel" v-loading="segmentIpsLoading">
          <div class="panel-title">
            <template v-if="activeSegment">
              {{ segmentLabel(activeSegment) }} · 空闲 {{ segmentFreeIps.length }} 条 · 当前勾选
              {{ pickKind === 'business' ? '业务' : 'BMC' }}
              {{ activeSelectedIds.length }}/{{ needCount }}
            </template>
            <template v-else>请先选择左侧地址段</template>
          </div>
          <el-empty
            v-if="activeSegmentId && !segmentFreeIps.length && !segmentIpsLoading"
            description="该段暂无空闲地址"
            :image-size="56"
          />
          <el-table
            v-else-if="segmentFreeIps.length"
            ref="ipTableRef"
            :data="segmentFreeIps"
            size="small"
            height="300"
            row-key="id"
            @selection-change="onIpTableSelectionChange"
          >
            <el-table-column type="selection" width="48" :selectable="ipRowSelectable" />
            <el-table-column prop="system_ip" label="IP 地址" min-width="130" />
            <el-table-column label="状态" min-width="120">
              <template #default="{ row }">
                <span :class="{ 'text-muted': otherSelectedIdSet.has(row.id) }">
                  {{ ipStatusLabel(row) }}
                </span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty
            v-else-if="!activeSegmentId"
            description="点击左侧地址段开始选择"
            :image-size="64"
          />
        </div>
      </div>

      <div v-if="!apply.clearVip" class="vip-row">
        <span class="vip-label">统一 VIP（可选）</span>
        <el-select
          v-model="selectedVipIpId"
          filterable
          clearable
          placeholder="从当前段空闲 IP 中选 1 条，所有设备共用"
          style="flex: 1"
        >
          <el-option
            v-for="ip in segmentFreeIps"
            :key="`vip-${ip.id}`"
            :label="ip.system_ip"
            :value="ip.id"
            :disabled="
              selectedBusinessIpIds.includes(ip.id) || selectedBmcIpIds.includes(ip.id)
            "
          />
        </el-select>
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" :disabled="!selectedCount" @click="submit">
        执行修改
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.hint {
  margin: 0 0 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.5;
}
.panel {
  padding: 4px 0;
}
.sub-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.sub-hint.warn {
  color: var(--el-color-warning);
}
.sub-hint.flush {
  margin: 0;
}
.pick-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.summary {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.clear-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
  margin-bottom: 10px;
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
.vip-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
}
.vip-label {
  flex-shrink: 0;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
</style>
