<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { TableInstance } from 'element-plus'
import {
  applyDeviceModelPanel,
  listDevices,
  listPanelCandidates,
  type DevicePanelCandidate,
} from '@/api/device'
import type { NetworkNode } from '@/api/network'

const props = defineProps<{
  modelValue: boolean
  node: NetworkNode | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  done: []
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const loading = ref(false)
const submitting = ref(false)
const candidates = ref<DevicePanelCandidate[]>([])
const unboundCount = ref(0)
const boundCount = ref(0)
const activeTab = ref<'apply' | 'modify'>('apply')
const selectedUnbound = ref<DevicePanelCandidate[]>([])
const selectedBound = ref<DevicePanelCandidate[]>([])
const unboundTableRef = ref<TableInstance>()
const boundTableRef = ref<TableInstance>()
const loadError = ref('')

const unboundRows = computed(() => candidates.value.filter((d) => !d.network_panel_bound))
const boundRows = computed(() => candidates.value.filter((d) => d.network_panel_bound))

function deviceLabel(row: DevicePanelCandidate) {
  return row.name || row.hostname
}

function locationText(row: DevicePanelCandidate) {
  const parts = [row.room_name, row.rack_code, row.u_position != null ? `${row.u_position}U` : null]
  return parts.filter(Boolean).join(' / ') || '-'
}

function onUnboundSelectionChange(rows: DevicePanelCandidate[]) {
  selectedUnbound.value = rows
}

function onBoundSelectionChange(rows: DevicePanelCandidate[]) {
  selectedBound.value = rows
}

async function selectAllUnbound() {
  await nextTick()
  unboundTableRef.value?.clearSelection()
  unboundRows.value.forEach((row) => {
    unboundTableRef.value?.toggleRowSelection(row, true)
  })
}

async function clearUnbound() {
  unboundTableRef.value?.clearSelection()
  selectedUnbound.value = []
}

async function selectAllBound() {
  await nextTick()
  boundTableRef.value?.clearSelection()
  boundRows.value.forEach((row) => {
    boundTableRef.value?.toggleRowSelection(row, true)
  })
}

async function clearBound() {
  boundTableRef.value?.clearSelection()
  selectedBound.value = []
}

/** 打开时默认全选当前页未绑定设备 */
async function autoSelectAllUnbound() {
  await nextTick()
  unboundTableRef.value?.clearSelection()
  unboundRows.value.forEach((row) => {
    unboundTableRef.value?.toggleRowSelection(row, true)
  })
}

async function loadCandidatesFromInventoryFallback(name: string, _modelId: string) {
  // 按采购汇总设备名称拉取并过滤（与后端 list_for_panel_apply 一致）
  const data = await listDevices({ page_size: 200, keyword: name || undefined })
  const key = name.trim().toLowerCase()
  const items = (data.items || []).filter((d) => {
    if (!key) return false
    const n = (d.name || '').trim().toLowerCase()
    const h = (d.hostname || '').trim().toLowerCase()
    return n === key || h === key || n.includes(key) || h.includes(key)
  })
  return items.map(
    (d): DevicePanelCandidate => ({
      id: d.id,
      name: d.name,
      hostname: d.hostname,
      serial_number: d.serial_number,
      device_model_id: d.device_model_id,
      device_model_name: d.device_model_name,
      network_panel_bound: !!d.network_panel_bound,
      rack_code: d.rack_code,
      room_name: d.room_name,
      u_position: d.u_position,
      status: d.status,
    }),
  )
}

async function loadCandidates() {
  const node = props.node
  loadError.value = ''
  if (!node?.device_model_id || !node.contract_device_name) {
    candidates.value = []
    loadError.value = '当前定义未关联合同设备名称，请先在上方选择「合同厂商型号采购汇总」'
    return
  }
  loading.value = true
  try {
    let items: DevicePanelCandidate[] = []
    try {
      const data = await listPanelCandidates(node.device_model_id, node.contract_device_name)
      items = data.items || []
      unboundCount.value = data.unbound_count
      boundCount.value = data.bound_count
    } catch {
      items = await loadCandidatesFromInventoryFallback(
        node.contract_device_name,
        node.device_model_id,
      )
      unboundCount.value = items.filter((d) => !d.network_panel_bound).length
      boundCount.value = items.filter((d) => d.network_panel_bound).length
    }
    candidates.value = items
    selectedUnbound.value = []
    selectedBound.value = []
    activeTab.value = unboundCount.value > 0 ? 'apply' : 'modify'
    if (!items.length) {
      loadError.value = `未找到设备名称为「${node.contract_device_name}」的台账（对应采购汇总设备名称），请先在设备管理中创建同名设备`
    }
    if (activeTab.value === 'apply' && unboundCount.value > 0) {
      await autoSelectAllUnbound()
    }
  } catch (err: unknown) {
    candidates.value = []
    const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
    loadError.value = msg || '加载可应用设备失败'
    ElMessage.error(loadError.value)
  } finally {
    loading.value = false
  }
}

async function submit(mode: 'apply' | 'modify', all = false) {
  const node = props.node
  if (!node?.port_layout || !node.device_model_id || !node.contract_device_name) {
    ElMessage.warning('请先完成面板定义并关联合同型号')
    return
  }
  const ids =
    mode === 'apply'
      ? all
        ? unboundRows.value.map((d) => d.id)
        : selectedUnbound.value.map((d) => d.id)
      : all
        ? boundRows.value.map((d) => d.id)
        : selectedBound.value.map((d) => d.id)

  if (!ids.length) {
    ElMessage.warning(mode === 'apply' ? '请先勾选要应用的设备，或点「全部应用」' : '请先勾选要修改的设备，或点「全部修改」')
    return
  }

  submitting.value = true
  try {
    const result = await applyDeviceModelPanel(node.device_model_id, {
      port_layout: node.port_layout as unknown as Record<string, unknown>,
      apply_device_name: node.contract_device_name,
      network_kind: node.kind,
      mode,
      device_ids: ids,
    })
    ElMessage.success(result.message || (mode === 'apply' ? '应用成功' : '修改成功'))
    emit('done')
    await loadCandidates()
  } catch (err: unknown) {
    const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
    ElMessage.error(msg || (mode === 'apply' ? '应用失败' : '修改失败'))
  } finally {
    submitting.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) void loadCandidates()
  },
)

watch(activeTab, async (tab) => {
  if (tab === 'apply' && unboundRows.value.length) {
    await autoSelectAllUnbound()
  }
})
</script>

<template>
  <el-dialog
    v-model="visible"
    title="应用面板到设备"
    width="860px"
    append-to-body
    destroy-on-close
    class="apply-panel-dialog"
  >
    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="hint-alert"
      :title="`采购汇总设备名称：${node?.contract_device_name || '-'}。「应用（未绑定）」仅列出设备管理中与该名称一致/相关的台账，可勾选单台或全部应用；已应用设备请到「修改」页签。`"
    />

    <div v-loading="loading" class="body">
      <el-alert
        v-if="loadError"
        type="warning"
        :closable="false"
        show-icon
        :title="loadError"
        class="hint-alert"
      />

      <el-tabs v-model="activeTab">
        <el-tab-pane :label="`应用（未绑定 ${unboundCount}）`" name="apply">
          <div class="toolbar">
            <el-button type="primary" plain size="small" :disabled="!unboundRows.length" @click="selectAllUnbound">
              全选
            </el-button>
            <el-button size="small" :disabled="!selectedUnbound.length" @click="clearUnbound">取消全选</el-button>
            <span class="count">已选 {{ selectedUnbound.length }} / {{ unboundRows.length }}</span>
          </div>
          <el-table
            ref="unboundTableRef"
            :data="unboundRows"
            row-key="id"
            height="320"
            border
            stripe
            empty-text="没有可应用的设备（设备管理中无与采购汇总设备名称对应的未绑定台账）"
            @selection-change="onUnboundSelectionChange"
          >
            <el-table-column type="selection" width="48" reserve-selection />
            <el-table-column label="设备名称" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ deviceLabel(row) }}</template>
            </el-table-column>
            <el-table-column prop="hostname" label="主机名" min-width="120" show-overflow-tooltip />
            <el-table-column prop="serial_number" label="序列号" min-width="120" show-overflow-tooltip />
            <el-table-column prop="device_model_name" label="型号" min-width="120" show-overflow-tooltip />
            <el-table-column label="位置" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ locationText(row) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default>
                <el-tag size="small" type="info">未应用</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`修改（已应用 ${boundCount}）`" name="modify">
          <div class="toolbar">
            <el-button type="warning" plain size="small" :disabled="!boundRows.length" @click="selectAllBound">
              全选
            </el-button>
            <el-button size="small" :disabled="!selectedBound.length" @click="clearBound">取消全选</el-button>
            <span class="count">已选 {{ selectedBound.length }} / {{ boundRows.length }}</span>
          </div>
          <el-table
            ref="boundTableRef"
            :data="boundRows"
            row-key="id"
            height="320"
            border
            stripe
            empty-text="尚无已应用面板的设备"
            @selection-change="onBoundSelectionChange"
          >
            <el-table-column type="selection" width="48" reserve-selection />
            <el-table-column label="设备名称" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ deviceLabel(row) }}</template>
            </el-table-column>
            <el-table-column prop="hostname" label="主机名" min-width="120" show-overflow-tooltip />
            <el-table-column prop="serial_number" label="序列号" min-width="120" show-overflow-tooltip />
            <el-table-column prop="device_model_name" label="型号" min-width="120" show-overflow-tooltip />
            <el-table-column label="位置" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ locationText(row) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default>
                <el-tag size="small" type="success">已应用</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <template v-if="activeTab === 'apply'">
        <el-button
          type="primary"
          plain
          :loading="submitting"
          :disabled="!unboundRows.length"
          @click="submit('apply', true)"
        >
          全部应用（{{ unboundRows.length }}）
        </el-button>
        <el-button
          type="primary"
          :loading="submitting"
          :disabled="!selectedUnbound.length"
          @click="submit('apply', false)"
        >
          应用选中（{{ selectedUnbound.length }}）
        </el-button>
      </template>
      <template v-else>
        <el-button
          type="warning"
          plain
          :loading="submitting"
          :disabled="!boundRows.length"
          @click="submit('modify', true)"
        >
          全部修改（{{ boundRows.length }}）
        </el-button>
        <el-button
          type="warning"
          :loading="submitting"
          :disabled="!selectedBound.length"
          @click="submit('modify', false)"
        >
          修改选中（{{ selectedBound.length }}）
        </el-button>
      </template>
    </template>
  </el-dialog>
</template>

<style scoped>
.hint-alert {
  margin-bottom: 12px;
}

.body {
  min-height: 260px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.count {
  font-size: 12px;
  color: #909399;
}
</style>
