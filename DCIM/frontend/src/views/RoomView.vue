<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listDatacenters, type DataCenter } from '@/api/datacenter'
import { listRacks, type Rack } from '@/api/rack'
import { createRoomQuick, deleteRoom, listRooms, updateRoom } from '@/api/room'
import type { Room } from '@/api/room'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const tableData = ref<Room[]>([])
const datacenters = ref<DataCenter[]>([])
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const keyword = ref('')
const dialogVisible = ref(false)
const editingId = ref<string | null>(null)
const layoutVisible = ref(false)
const layoutLoading = ref(false)
const layoutRoom = ref<Room | null>(null)
const layoutRacks = ref<Rack[]>([])

interface LayoutSlot {
  row: number
  col: number
  code: string
  rack: Rack | null
}

const layoutRows = computed(() => {
  const room = layoutRoom.value
  if (!room) return [] as Array<{ row: number; label: string; slots: LayoutSlot[] }>
  const layout =
    room.row_layout?.length > 0
      ? room.row_layout
      : Array.from({ length: room.rack_rows }, () => room.rack_columns)
  const codes = room.slot_codes || []
  const rackMap = new Map(layoutRacks.value.map((r) => [`${r.row_no}-${r.column_no}`, r]))

  return layout.map((cols, idx) => {
    const row = idx + 1
    const slots: LayoutSlot[] = Array.from({ length: cols }, (_, colIdx) => {
      const col = colIdx + 1
      const code = codes[idx]?.[colIdx] || `R${String(row).padStart(2, '0')}${String(col).padStart(2, '0')}`
      return {
        row,
        col,
        code,
        rack: rackMap.get(`${row}-${col}`) || null,
      }
    })
    const label = codes[idx]?.[0]?.replace(/\d+$/, '') || `第${row}排`
    return { row, label, slots }
  })
})

const layoutStats = computed(() => {
  const total = layoutRows.value.reduce((sum, r) => sum + r.slots.length, 0)
  const occupied = layoutRows.value.reduce(
    (sum, r) => sum + r.slots.filter((s) => s.rack).length,
    0,
  )
  return { total, occupied, free: total - occupied }
})

const form = reactive({
  datacenter_id: '',
  building_no: '',
  room_no: '',
  layout_mode: 'auto' as 'auto' | 'manual',
  rack_rows: 4,
  rack_columns: 6,
  row_layout: [6, 6, 6, 6] as number[],
  code_mode: 'auto' as 'auto' | 'custom',
  code_prefix: 'A',
  slot_codes: [] as string[][],
  description: '',
})

const activeLayout = computed(() =>
  form.layout_mode === 'auto'
    ? Array.from({ length: form.rack_rows }, () => form.rack_columns)
    : form.row_layout,
)

const rackCapacity = computed(() => activeLayout.value.reduce((sum, n) => sum + n, 0))

const layoutSummary = computed(() => {
  const layout = activeLayout.value
  if (form.layout_mode === 'auto') {
    return `${form.rack_rows} 排 × ${form.rack_columns} 列（共 ${rackCapacity.value} 位）`
  }
  return `${layout.length} 排（${layout.join('+')}，共 ${rackCapacity.value} 位）`
})

const rowPrefixResult = computed(() => {
  try {
    return { ok: true as const, prefixes: expandRowPrefixes(form.code_prefix, activeLayout.value.length) }
  } catch (error) {
    return { ok: false as const, message: error instanceof Error ? error.message : '前缀无效', prefixes: [] as string[] }
  }
})

const codePreview = computed(() => {
  if (form.code_mode === 'auto' && !rowPrefixResult.value.ok) {
    return rowPrefixResult.value.message
  }
  const codes = form.slot_codes.flat().filter(Boolean)
  if (!codes.length) return '—'
  if (codes.length <= 8) return codes.join('、')
  return `${codes.slice(0, 8).join('、')} …（共 ${codes.length} 个）`
})

const rowPrefixHint = computed(() => {
  if (!rowPrefixResult.value.ok) return rowPrefixResult.value.message
  const prefixes = rowPrefixResult.value.prefixes
  const map = prefixes.map((p, i) => `第${i + 1}排=${p}`).join('，')
  const sample = prefixes[0] ? `${prefixes[0]}01、${prefixes[0]}02` : ''
  return `排前缀：${map}；同排示例：${sample}`
})

const canCreate = auth.hasPermission('datacenter:create')
const canUpdate = auth.hasPermission('datacenter:update')
const canDelete = auth.hasPermission('datacenter:delete')

function datacenterLabel(dc: DataCenter) {
  return dc.location ? `${dc.name}（${dc.location}）` : dc.name
}

function letterToIndex(label: string): number {
  const text = label.trim().toUpperCase()
  if (!text || !/^[A-Z]+$/.test(text)) {
    throw new Error(`无效字母标签：${label}`)
  }
  let value = 0
  for (const ch of text) {
    value = value * 26 + (ch.charCodeAt(0) - 64)
  }
  return value
}

function indexToLetter(index: number): string {
  if (index < 1) throw new Error('字母序号无效')
  let n = index
  let result = ''
  while (n > 0) {
    const rem = (n - 1) % 26
    result = String.fromCharCode(65 + rem) + result
    n = Math.floor((n - 1) / 26)
  }
  return result
}

function expandRowPrefixes(expression: string, rowCount: number): string[] {
  if (rowCount < 1) throw new Error('排数无效')
  let raw = (expression || 'A').trim().toUpperCase().replace(/\s+/g, '')
  if (!raw) raw = 'A'

  if (raw.includes('-')) {
    const [startRaw, endRaw] = raw.split('-', 2)
    if (!startRaw || !endRaw) throw new Error('范围格式应为 A-D 或 A-BZ')
    const start = letterToIndex(startRaw)
    const end = letterToIndex(endRaw)
    if (end < start) throw new Error('范围终点必须大于等于起点')
    const labels: string[] = []
    for (let i = start; i <= end; i += 1) labels.push(indexToLetter(i))
    if (labels.length < rowCount) {
      throw new Error(`范围 ${raw} 仅有 ${labels.length} 个字母，但机房有 ${rowCount} 排`)
    }
    return labels.slice(0, rowCount)
  }

  const start = letterToIndex(raw)
  return Array.from({ length: rowCount }, (_, i) => indexToLetter(start + i))
}

function buildSlotCodes(layout: number[], prefixExpr = form.code_prefix, keepExisting = true): string[][] {
  if (form.code_mode === 'custom' && keepExisting) {
    return layout.map((cols, rowIdx) => {
      const existing = form.slot_codes[rowIdx] || []
      return Array.from({ length: cols }, (_, colIdx) => existing[colIdx] || '')
    })
  }

  const prefixes = expandRowPrefixes(prefixExpr, layout.length)
  return layout.map((cols, rowIdx) => {
    const prefix = prefixes[rowIdx]
    const width = Math.max(2, String(cols).length)
    return Array.from({ length: cols }, (_, colIdx) => {
      const seq = String(colIdx + 1).padStart(width, '0')
      return `${prefix}${seq}`
    })
  })
}

function syncAutoLayout() {
  form.row_layout = Array.from({ length: form.rack_rows }, () => form.rack_columns)
}

function regenerateCodes(keepCustom = false) {
  try {
    form.slot_codes = buildSlotCodes(activeLayout.value, form.code_prefix, keepCustom)
  } catch {
    if (form.code_mode === 'auto') {
      form.slot_codes = []
    }
  }
}

watch(
  () => [form.rack_rows, form.rack_columns, form.layout_mode] as const,
  () => {
    if (form.layout_mode === 'auto') {
      syncAutoLayout()
    }
    regenerateCodes(form.code_mode === 'custom')
  },
)

watch(
  () => form.row_layout.join(','),
  () => {
    if (form.layout_mode === 'manual') {
      regenerateCodes(form.code_mode === 'custom')
    }
  },
)

watch(
  () => form.code_prefix,
  () => {
    if (form.code_mode === 'auto') {
      regenerateCodes(false)
    }
  },
)

watch(
  () => form.code_mode,
  (mode) => {
    regenerateCodes(mode === 'custom')
  },
)

function addManualRow() {
  form.row_layout.push(6)
}

function removeManualRow(index: number) {
  if (form.row_layout.length <= 1) {
    ElMessage.warning('至少保留一排')
    return
  }
  form.row_layout.splice(index, 1)
  form.slot_codes.splice(index, 1)
}

async function loadDatacenters() {
  const data = await listDatacenters({ page_size: 100 })
  datacenters.value = data.items
}

async function loadData() {
  loading.value = true
  try {
    const data = await listRooms({
      page: pagination.page,
      page_size: pagination.page_size,
      keyword: keyword.value || undefined,
    })
    tableData.value = data.items
    pagination.total = data.pagination.total
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.datacenter_id = datacenters.value[0]?.id || ''
  form.building_no = ''
  form.room_no = ''
  form.layout_mode = 'auto'
  form.rack_rows = 4
  form.rack_columns = 6
  form.code_mode = 'auto'
  form.code_prefix = 'A'
  syncAutoLayout()
  regenerateCodes(false)
  form.description = ''
  dialogVisible.value = true
}

function openEdit(row: Room) {
  editingId.value = row.id
  form.datacenter_id = row.datacenter_id || ''
  form.building_no = row.building_no || ''
  form.room_no = row.room_no || row.name
  form.layout_mode = row.layout_mode === 'manual' ? 'manual' : 'auto'
  form.rack_rows = row.rack_rows
  form.rack_columns = row.rack_columns
  form.row_layout = [...(row.row_layout?.length ? row.row_layout : [row.rack_columns])]
  form.code_mode = row.code_mode === 'custom' ? 'custom' : 'auto'
  form.code_prefix = row.code_prefix || 'A'
  form.slot_codes = row.slot_codes?.length
    ? row.slot_codes.map((r) => [...r])
    : buildSlotCodes(form.row_layout, form.code_prefix, false)
  form.description = row.description || ''
  dialogVisible.value = true
}

function formatLayout(row: Room) {
  const layout = row.row_layout?.length ? row.row_layout : Array(row.rack_rows).fill(row.rack_columns)
  const uniform = layout.every((n) => n === layout[0])
  if (uniform) {
    return `${layout.length} 排 × ${layout[0]} 列（共 ${row.rack_capacity} 位）`
  }
  return `${layout.length} 排（${layout.join('+')}，共 ${row.rack_capacity} 位）`
}

async function handleSubmit() {
  if (!editingId.value && !form.datacenter_id) {
    ElMessage.warning('请选择数据中心（地理位置）')
    return
  }
  if (!form.building_no || !form.room_no) {
    ElMessage.warning('请填写机房楼号和机房编号')
    return
  }
  if (form.layout_mode === 'manual') {
    if (!form.row_layout.length || form.row_layout.some((n) => n < 1)) {
      ElMessage.warning('请为每一排设置有效的机柜数量')
      return
    }
  } else if (form.rack_rows < 1 || form.rack_columns < 1) {
    ElMessage.warning('请填写有效的机柜排数和每排机柜数')
    return
  }

  const layout = activeLayout.value
  const slotCodes = form.slot_codes
  if (form.code_mode === 'auto' && !rowPrefixResult.value.ok) {
    ElMessage.warning(rowPrefixResult.value.message)
    return
  }
  if (form.code_mode === 'custom') {
    const flat = slotCodes.flat()
    if (flat.some((c) => !c?.trim())) {
      ElMessage.warning('请填写全部机柜编号')
      return
    }
    const lower = flat.map((c) => c.trim().toLowerCase())
    if (new Set(lower).size !== lower.length) {
      ElMessage.warning('机柜编号不能重复')
      return
    }
  }

  const layoutPayload =
    form.layout_mode === 'auto'
      ? {
          layout_mode: 'auto' as const,
          rack_rows: form.rack_rows,
          rack_columns: form.rack_columns,
          row_layout: layout,
        }
      : {
          layout_mode: 'manual' as const,
          row_layout: [...form.row_layout],
          rack_rows: form.row_layout.length,
          rack_columns: Math.max(...form.row_layout),
        }

  const codePayload = {
    code_mode: form.code_mode,
    code_prefix: form.code_prefix || 'A',
    slot_codes:
      form.code_mode === 'custom'
        ? slotCodes.map((r) => r.map((c) => c.trim()))
        : buildSlotCodes(layout, form.code_prefix, false),
  }

  try {
    if (editingId.value) {
      await updateRoom(editingId.value, {
        room_no: form.room_no,
        description: form.description || null,
        ...layoutPayload,
        ...codePayload,
      })
      ElMessage.success('更新成功')
    } else {
      const created = await createRoomQuick({
        datacenter_id: form.datacenter_id,
        building_no: form.building_no,
        room_no: form.room_no,
        description: form.description || null,
        ...layoutPayload,
        ...codePayload,
      })
      ElMessage.success('创建成功')
      dialogVisible.value = false
      await loadData()
      await openLayout(created)
      return
    }
    dialogVisible.value = false
    await loadData()
  } catch (error: unknown) {
    const err = error as {
      response?: { data?: { message?: string; details?: { errors?: Array<{ msg?: string; loc?: unknown }> } } }
      message?: string
    }
    const details = err.response?.data?.details?.errors
    const detailMsg = details?.map((e) => e.msg).filter(Boolean).join('；')
    const message = detailMsg || err.response?.data?.message || err.message || '操作失败'
    ElMessage.error(message)
  }
}

function roomTitle(row: Room) {
  return [row.datacenter_name || row.location, row.building_no, row.room_no || row.name]
    .filter(Boolean)
    .join('-')
}

function utilizationClass(rack: Rack | null) {
  if (!rack) return 'empty'
  if (rack.utilization >= 80) return 'high'
  if (rack.utilization >= 40) return 'mid'
  if (rack.utilization > 0) return 'low'
  return 'idle'
}

async function openLayout(row: Room) {
  layoutRoom.value = row
  layoutVisible.value = true
  layoutLoading.value = true
  try {
    const data = await listRacks({ room_id: row.id, page_size: 500 })
    layoutRacks.value = data.items
  } catch (error: unknown) {
    layoutRacks.value = []
    const err = error as {
      response?: { data?: { message?: string; detail?: string } }
      message?: string
    }
    ElMessage.error(err.response?.data?.message || err.response?.data?.detail || err.message || '加载机柜数据失败')
  } finally {
    layoutLoading.value = false
  }
}

async function handleDelete(row: Room) {
  const label = [row.location || row.datacenter_name, row.building_no, row.room_no || row.name]
    .filter(Boolean)
    .join('-')
  await ElMessageBox.confirm(`确定删除机房「${label}」吗？`, '确认删除', { type: 'warning' })
  await deleteRoom(row.id)
  ElMessage.success('删除成功')
  await loadData()
}

onMounted(() => {
  void Promise.all([loadDatacenters(), loadData()])
})
</script>

<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>机房管理</span>
          <div class="actions">
            <el-input
              v-model="keyword"
              placeholder="搜索机房编号"
              clearable
              style="width: 220px"
              @keyup.enter="loadData"
              @clear="loadData"
            />
            <el-button @click="loadData">搜索</el-button>
            <el-button v-if="canCreate" type="primary" @click="openCreate">新建</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" stripe>
        <el-table-column label="数据中心" min-width="150">
          <template #default="{ row }">
            {{ row.datacenter_name || row.location || '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="building_no" label="机房楼号" min-width="100" />
        <el-table-column label="机房编号" min-width="100">
          <template #default="{ row }">{{ row.room_no || row.name }}</template>
        </el-table-column>
        <el-table-column label="机柜布局" min-width="180">
          <template #default="{ row }">{{ formatLayout(row) }}</template>
        </el-table-column>
        <el-table-column label="机柜编号" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            {{
              row.slot_codes?.length
                ? `${row.code_mode === 'custom' ? '自定义' : '自动'}：${row.slot_codes.flat().slice(0, 4).join('、')}${row.slot_codes.flat().length > 4 ? '…' : ''}`
                : '—'
            }}
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="120" show-overflow-tooltip />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openLayout(row)">布局图</el-button>
            <el-button v-if="canUpdate" type="primary" link @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canDelete" type="danger" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          layout="total, prev, pager, next"
          :total="pagination.total"
          @change="loadData"
        />
      </div>
    </el-card>

    <el-drawer
      v-model="layoutVisible"
      :title="layoutRoom ? `机房布局图 - ${roomTitle(layoutRoom)}` : '机房布局图'"
      size="720px"
    >
      <div v-loading="layoutLoading" class="floorplan">
        <div class="floorplan-summary">
          <span>机柜位 {{ layoutStats.total }}</span>
          <span>已建 {{ layoutStats.occupied }}</span>
          <span>空闲 {{ layoutStats.free }}</span>
        </div>
        <div class="floorplan-legend">
          <span><i class="dot empty" />空闲位</span>
          <span><i class="dot idle" />已建(空载/空闲U满)</span>
          <span><i class="dot low" />有设备·利用率&lt;40%</span>
          <span><i class="dot mid" />40%–80%</span>
          <span><i class="dot high" />≥80%</span>
        </div>

        <div v-if="layoutRows.length" class="floorplan-map">
          <div v-for="row in layoutRows" :key="row.row" class="floorplan-row">
            <div class="floorplan-row-label">第 {{ row.row }} 排</div>
            <div class="floorplan-slots">
              <div
                v-for="slot in row.slots"
                :key="`${slot.row}-${slot.col}`"
                class="rack-cell"
                :class="utilizationClass(slot.rack)"
              >
                <div class="rack-code">{{ slot.rack?.code || slot.code }}</div>
                <div class="rack-meta">
                  <template v-if="slot.rack">
                    {{ slot.rack.device_count ?? 0 }}台 · 空闲{{ slot.rack.free_u }}U · {{ slot.rack.utilization }}%
                  </template>
                  <template v-else>空闲位</template>
                </div>
              </div>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无布局数据" />
      </div>
    </el-drawer>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑机房' : '新建机房'" width="720px">
      <el-form label-width="110px">
        <el-form-item label="地理位置" required>
          <el-select
            v-model="form.datacenter_id"
            placeholder="选择已建数据中心"
            style="width: 100%"
            :disabled="!!editingId"
            filterable
          >
            <el-option
              v-for="dc in datacenters"
              :key="dc.id"
              :label="datacenterLabel(dc)"
              :value="dc.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="机房楼号" required>
          <el-input v-model="form.building_no" placeholder="例如：A栋" :disabled="!!editingId" />
        </el-form-item>
        <el-form-item label="机房编号" required>
          <el-input v-model="form.room_no" placeholder="例如：101" />
        </el-form-item>

        <el-form-item label="布局方式" required>
          <el-radio-group v-model="form.layout_mode">
            <el-radio value="auto">自动</el-radio>
            <el-radio value="manual">手动</el-radio>
          </el-radio-group>
        </el-form-item>

        <template v-if="form.layout_mode === 'auto'">
          <el-form-item label="机柜排数" required>
            <el-input-number v-model="form.rack_rows" :min="1" :max="50" style="width: 100%" />
          </el-form-item>
          <el-form-item label="每排机柜数" required>
            <el-input-number v-model="form.rack_columns" :min="1" :max="50" style="width: 100%" />
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item label="排布局" required>
            <div class="manual-layout">
              <div v-for="(_, index) in form.row_layout" :key="index" class="manual-row">
                <span class="row-label">第 {{ index + 1 }} 排</span>
                <el-input-number v-model="form.row_layout[index]" :min="1" :max="50" />
                <span class="row-unit">个机柜</span>
                <el-button type="danger" link @click="removeManualRow(index)">删除</el-button>
              </div>
              <el-button type="primary" plain @click="addManualRow">增加一排</el-button>
            </div>
          </el-form-item>
        </template>

        <el-form-item label="机柜容量">
          <el-input :model-value="layoutSummary" disabled />
        </el-form-item>

        <el-form-item label="机柜编号" required>
          <el-radio-group v-model="form.code_mode">
            <el-radio value="auto">自动生成</el-radio>
            <el-radio value="custom">自定义</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="form.code_mode === 'auto'" label="编号前缀" required>
          <el-input
            v-model="form.code_prefix"
            placeholder="单个字母如 A，或范围如 A-D / A-BZ"
            maxlength="20"
          />
          <div class="field-hint">
            单个字母：从该字母起按排递增（4 排填 A → A/B/C/D）。
            范围：如 A-D、A-BZ，字母数量需 ≥ 机柜排数。
            同排编号 = 排字母 + 序号（如 A01、A02）。
          </div>
          <div class="field-hint">{{ rowPrefixHint }}</div>
        </el-form-item>

        <el-form-item v-else label="逐位编号" required>
          <div class="slot-codes">
            <div v-for="(row, rowIdx) in form.slot_codes" :key="rowIdx" class="slot-row">
              <div class="slot-row-title">第 {{ rowIdx + 1 }} 排</div>
              <div class="slot-inputs">
                <el-input
                  v-for="(_, colIdx) in row"
                  :key="`${rowIdx}-${colIdx}`"
                  v-model="form.slot_codes[rowIdx][colIdx]"
                  :placeholder="`列${colIdx + 1}`"
                  size="small"
                  style="width: 88px"
                />
              </div>
            </div>
          </div>
          <div class="field-hint">可为每个机柜位单独命名，编号不可重复</div>
        </el-form-item>

        <el-form-item label="编号预览">
          <el-input :model-value="codePreview" disabled />
        </el-form-item>

        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存</el-button>
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
}

.actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.field-hint {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}

.manual-layout {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.manual-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.row-label {
  width: 64px;
  color: #606266;
}

.row-unit {
  color: #909399;
  font-size: 13px;
}

.slot-codes {
  width: 100%;
  max-height: 280px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 8px 0;
}

.slot-row-title {
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
}

.slot-inputs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.floorplan {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 240px;
}

.floorplan-summary {
  display: flex;
  gap: 20px;
  color: #606266;
  font-size: 14px;
}

.floorplan-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  font-size: 12px;
  color: #909399;
}

.floorplan-legend .dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  margin-right: 6px;
  vertical-align: middle;
}

.floorplan-legend .dot.empty,
.rack-cell.empty {
  background: #f5f7fa;
  border-color: #dcdfe6;
}

.floorplan-legend .dot.idle,
.rack-cell.idle {
  background: #ecf5ff;
  border-color: #b3d8ff;
}

.floorplan-legend .dot.low,
.rack-cell.low {
  background: #f0f9eb;
  border-color: #c2e7b0;
}

.floorplan-legend .dot.mid,
.rack-cell.mid {
  background: #fdf6ec;
  border-color: #f5dab1;
}

.floorplan-legend .dot.high,
.rack-cell.high {
  background: #fef0f0;
  border-color: #fbc4c4;
}

.floorplan-map {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.floorplan-row-label {
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.floorplan-slots {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.rack-cell {
  width: 96px;
  min-height: 72px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-sizing: border-box;
}

.rack-code {
  font-weight: 600;
  font-size: 13px;
  color: #303133;
  word-break: break-all;
}

.rack-meta {
  font-size: 12px;
  color: #909399;
}
</style>
