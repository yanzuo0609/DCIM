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
import { listIpAddresses, type IpAddress } from '@/api/ip'
import type { Rack } from '@/api/rack'
import type { Room } from '@/api/room'
import RackRangePicker from '@/components/RackRangePicker.vue'

const props = defineProps<{
  modelValue: boolean
  rooms: Room[]
  racks: Rack[]
  models: DeviceModel[]
  types: DeviceType[]
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
const ipTableRef = ref<{
  clearSelection: () => void
  toggleRowSelection: (row: IpAddress, selected?: boolean) => void
} | null>(null)
const allIps = ref<IpAddress[]>([])
const selectedIpIds = ref<string[]>([])
const ipRangeText = ref('')
const ipRangeError = ref('')

const form = reactive({
  count: 4,
  name_prefix: 'SRV',
  serial_prefix: 'SN',
  start_index: 1,
  device_model_id: '',
  device_type_id: '' as string | null,
  height_u: 1 as number | null,
  room_id: '',
  rack_ids: [] as string[],
  start_u: 1,
  gap_u: 1,
  per_rack_count: 60,
})

const previewRows = ref<BatchMountNewDevice[]>([])
const previewLines = ref<string[]>([])

const roomRacks = computed(() => props.racks.filter((r) => r.room_id === form.room_id))

const sortedIps = computed(() =>
  [...allIps.value].sort((a, b) => ipToNum(a.system_ip) - ipToNum(b.system_ip)),
)

const unboundIps = computed(() =>
  sortedIps.value.filter((ip) => !ip.device_id && ip.status !== 'disabled' && ip.status !== 'allocated'),
)

const selectedIpSummary = computed(() => {
  const selected = sortedIps.value.filter((ip) => selectedIpIds.value.includes(ip.id))
  if (!selected.length) return '未选择 IP（可跳过，后续再关联）'
  return `已选 ${selected.length} 条未绑定 IP`
})

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
  const rows: BatchMountNewDevice[] = []
  for (let i = 0; i < form.count; i += 1) {
    const idx = form.start_index + i
    const name = `${form.name_prefix}${padIndex(idx)}`
    rows.push({
      name,
      hostname: name,
      serial_number: `${form.serial_prefix}${padIndex(idx)}`,
      device_model_id: form.device_model_id,
      device_type_id: form.device_type_id,
      height_u: form.height_u || model?.height_u || 1,
    })
  }
  return rows
}

async function loadIps() {
  if (ipLoading.value) return
  ipLoading.value = true
  try {
    const pages: IpAddress[] = []
    let page = 1
    let total = 0
    do {
      // 仅拉取空闲 IP，减少批量新建弹窗首屏等待
      const data = await listIpAddresses({ page, page_size: 200, status: 'free' })
      pages.push(...(data.items || []))
      total = data.pagination?.total ?? pages.length
      page += 1
    } while (pages.length < total && page <= 10)
    allIps.value = pages
  } catch {
    allIps.value = []
    ElMessage.error('加载 IP 列表失败')
  } finally {
    ipLoading.value = false
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
  form.room_id = props.rooms[0]?.id || ''
  form.rack_ids = []
  form.start_u = 1
  form.gap_u = 1
  form.per_rack_count = 60
  selectedIpIds.value = []
  ipRangeText.value = ''
  ipRangeError.value = ''
  previewRows.value = []
  previewLines.value = []
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    resetForm()
    allIps.value = []
  },
)

watch(
  () => form.device_model_id,
  (id) => {
    const model = props.models.find((m) => m.id === id)
    if (model) form.height_u = model.height_u
  },
)

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
  () => {
    form.rack_ids = form.rack_ids.filter((id) => roomRacks.value.some((r) => r.id === id))
  },
)

async function applyIpRange() {
  ipRangeError.value = ''
  const text = ipRangeText.value.trim()
  if (!text) {
    selectedIpIds.value = []
    ipTableRef.value?.clearSelection()
    return
  }

  const rangeMatch = text.match(/^(.+?)\s*[-~～—–到至]\s*(.+)$/)
  let startIp: string
  let endIp: string
  if (rangeMatch) {
    startIp = rangeMatch[1].trim()
    endIp = rangeMatch[2].trim()
  } else if (/^\d+\.\d+\.\d+\.\d+$/.test(text)) {
    startIp = text
    endIp = text
  } else {
    ipRangeError.value = '请输入如 192.168.1.10-192.168.1.20 的范围'
    return
  }

  const startN = ipToNum(startIp)
  const endN = ipToNum(endIp)
  if (startN === Number.MAX_SAFE_INTEGER || endN === Number.MAX_SAFE_INTEGER) {
    ipRangeError.value = 'IP 格式无效'
    return
  }
  if (startN > endN) {
    ipRangeError.value = '起始 IP 不能大于结束 IP'
    return
  }

  const inRange = unboundIps.value.filter((ip) => {
    const n = ipToNum(ip.system_ip)
    return n >= startN && n <= endN
  })
  if (!inRange.length) {
    ipRangeError.value = '该范围内没有可关联的未绑定 IP（请先批量生成 IP）'
    return
  }
  selectedIpIds.value = inRange.map((ip) => ip.id)
  await nextTick()
  ipTableRef.value?.clearSelection()
  for (const row of inRange) {
    ipTableRef.value?.toggleRowSelection(row, true)
  }
  ElMessage.success(`已选中范围内 ${inRange.length} 条未绑定 IP`)
}

function onIpSelectionChange(rows: IpAddress[]) {
  selectedIpIds.value = rows.filter((r) => !r.device_id).map((r) => r.id)
}

function ipRowSelectable(row: IpAddress) {
  return !row.device_id && row.status !== 'disabled' && row.status !== 'allocated'
}

function bindLabel(row: IpAddress) {
  if (row.status === 'disabled') return '已禁用'
  if (row.status === 'allocated' || row.device_id) {
    return row.device_name ? `已分配 · ${row.device_name}` : '已分配'
  }
  if (row.bind_type === 'rack') return `机柜 ${row.rack_code || ''}`
  if (row.bind_type === 'rack_range') return '机柜范围'
  return '空闲'
}

function buildPreview() {
  previewRows.value = buildDeviceRows()
  const targets = form.rack_ids.length
    ? roomRacks.value.filter((r) => form.rack_ids.includes(r.id))
    : roomRacks.value
  const roomName = props.rooms.find((r) => r.id === form.room_id)?.name || ''
  const ips = sortedIps.value.filter((ip) => selectedIpIds.value.includes(ip.id))
  previewLines.value = [
    `机房：${roomName}`,
    `新建设备：${previewRows.value.length} 台（${previewRows.value[0]?.name || '-'} … ${previewRows.value.at(-1)?.name || '-'}）`,
    `关联 IP：${ips.length} 条${ips.length ? `（${ips[0].system_ip} … ${ips.at(-1)?.system_ip}）` : '（跳过）'}`,
    `目标机柜：${targets.length} 台`,
    `起始 U：${form.start_u}，设备间隔：${form.gap_u}U，每柜最多：${form.per_rack_count} 台`,
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
      ElMessage.warning('请填写名称前缀与序列号前缀')
      return
    }
    step.value = 1
    await loadIps()
    return
  }
  if (step.value === 1) {
    if (selectedIpIds.value.length && selectedIpIds.value.length !== form.count) {
      ElMessage.warning(
        `已选 IP ${selectedIpIds.value.length} 条，与设备数量 ${form.count} 不一致；将按较少一方配对关联`,
      )
    }
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
      ip_ids: selectedIpIds.value,
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
    width="820px"
    destroy-on-close
    top="4vh"
  >
    <el-steps :active="step" finish-status="success" align-center style="margin-bottom: 20px">
      <el-step title="设备信息" />
      <el-step title="IP 范围" />
      <el-step title="机柜上架" />
      <el-step title="确认提交" />
    </el-steps>

    <div v-if="step === 0">
      <el-form label-width="110px">
        <el-form-item label="新建数量" required>
          <el-input-number v-model="form.count" :min="1" :max="200" />
        </el-form-item>
        <el-form-item label="起始序号">
          <el-input-number v-model="form.start_index" :min="1" :max="9999" />
        </el-form-item>
        <el-form-item label="名称前缀" required>
          <el-input v-model="form.name_prefix" placeholder="如 SRV → SRV01" />
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
        :title="`预览：${form.name_prefix}${padIndex(form.start_index)} … ${form.name_prefix}${padIndex(form.start_index + form.count - 1)}`"
      />
    </div>

    <div v-else-if="step === 1" v-loading="ipLoading">
      <el-form label-width="90px" style="margin-bottom: 12px">
        <el-form-item label="IP 范围">
          <div class="ip-range-row">
            <el-input
              v-model="ipRangeText"
              clearable
              placeholder="从已有 IP 中选择，如 192.168.1.10-192.168.1.20"
              @keyup.enter="applyIpRange"
            />
            <el-button type="primary" plain @click="applyIpRange">应用范围</el-button>
          </div>
        </el-form-item>
      </el-form>
      <p v-if="ipRangeError" class="range-error">{{ ipRangeError }}</p>
      <p class="hint">
        下列为系统中已新建的 IP；灰色行为已关联，仅可勾选未绑定 IP。也可跳过本步稍后关联。
      </p>
      <p class="hint">{{ selectedIpSummary }} · 未绑定 {{ unboundIps.length }} / 共 {{ sortedIps.length }}</p>
      <el-table
        ref="ipTableRef"
        :data="sortedIps"
        height="320"
        size="small"
        row-key="id"
        @selection-change="onIpSelectionChange"
      >
        <el-table-column type="selection" width="42" :selectable="ipRowSelectable" />
        <el-table-column prop="system_ip" label="系统 IP" min-width="120" />
        <el-table-column prop="bmc_ip" label="BMC" min-width="110">
          <template #default="{ row }">{{ row.bmc_ip || '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" min-width="120">
          <template #default="{ row }">
            <span :class="{ 'text-muted': !!row.device_id }">{{ bindLabel(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="label" label="标签" min-width="90">
          <template #default="{ row }">{{ row.label || '—' }}</template>
        </el-table-column>
      </el-table>
    </div>

    <div v-else-if="step === 2">
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
          <el-input-number v-model="form.per_rack_count" :min="1" :max="60" />
        </el-form-item>
      </el-form>
      <el-alert
        type="info"
        :closable="false"
        title="按机柜编号顺序上架；每柜从起始 U 起放置，设备间保留间隔；位置图与机柜设备数量将同步更新"
      />
    </div>

    <div v-else>
      <ul class="preview-list">
        <li v-for="(line, i) in previewLines" :key="i">{{ line }}</li>
      </ul>
      <el-table v-if="previewRows.length" :data="previewRows.slice(0, 8)" size="small" style="margin-top: 12px">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="serial_number" label="序列号" />
        <el-table-column label="关联 IP（按序）">
          <template #default="{ $index }">
            {{
              sortedIps.filter((ip) => selectedIpIds.includes(ip.id))[$index]?.system_ip || '—'
            }}
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
}
.ip-range-row .el-input {
  flex: 1;
}
.range-error {
  margin: 0 0 8px;
  color: var(--el-color-danger);
  font-size: 12px;
}
.hint {
  margin: 0 0 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
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
</style>
