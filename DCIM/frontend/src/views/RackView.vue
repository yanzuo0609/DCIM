<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listRooms } from '@/api/room'
import type { Room } from '@/api/room'
import {
  applyTemplateToRoom,
  batchDeleteRacks,
  checkRackCode,
  createRackTemplate,
  deleteRack,
  deleteRackTemplate,
  getRackLayout,
  listRackTemplates,
  listRacks,
  placeRacksBatch,
  unapplyTemplateFromRoom,
  updateRack,
  updateRackTemplate,
  type Rack,
  type RackCodeCheck,
  type RackLayoutSlot,
  type RackTemplate,
} from '@/api/rack'
import { useAuthStore } from '@/stores/auth'
import RackCabinet from '@/components/RackCabinet.vue'

const auth = useAuthStore()
const activeTab = ref<'templates' | 'racks'>('templates')

const loading = ref(false)
const tableData = ref<Rack[]>([])
const rooms = ref<Room[]>([])
const templates = ref<RackTemplate[]>([])
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const keyword = ref('')
const roomFilter = ref('')
const rackSort = reactive<{ sort: string; order: 'asc' | 'desc' }>({
  sort: 'code',
  order: 'asc',
})
const selectedRacks = ref<Rack[]>([])
const batchDeleting = ref(false)
const rackTableRef = ref<{ clearSelection: () => void } | null>(null)

const layoutVisible = ref(false)
const layoutLoading = ref(false)
const exportLoading = ref(false)
const layoutSlots = ref<RackLayoutSlot[]>([])
const layoutRack = ref<Rack | null>(null)
const layoutTotalPower = ref(0)

const canCreate = auth.hasPermission('rack:create')
const canUpdate = auth.hasPermission('rack:update')
const canDelete = auth.hasPermission('rack:delete')

const statusOptions = [
  { label: '运行中', value: 'active' },
  { label: '停用', value: 'inactive' },
  { label: '维护中', value: 'maintenance' },
]

function roomName(roomId: string) {
  return rooms.value.find((r) => r.id === roomId)?.name || roomId
}

function templateName(templateId: string | null) {
  if (!templateId) return '—'
  return templates.value.find((t) => t.id === templateId)?.name || templateId
}

function statusLabel(status: string) {
  return statusOptions.find((s) => s.value === status)?.label || status
}

function roomLabel(room: Room) {
  const parts = [room.location, room.building_no, room.room_no || room.name].filter(Boolean)
  return parts.length ? parts.join('-') : room.name
}

function clearRackSelection() {
  selectedRacks.value = []
  rackTableRef.value?.clearSelection()
}

function onRackSelectionChange(rows: Rack[]) {
  selectedRacks.value = rows
}

function onRackSortChange(payload: { prop: string; order: 'ascending' | 'descending' | null }) {
  if (payload.prop === 'code' && payload.order) {
    rackSort.sort = 'code'
    rackSort.order = payload.order === 'ascending' ? 'asc' : 'desc'
  } else {
    rackSort.sort = 'code'
    rackSort.order = 'asc'
  }
  pagination.page = 1
  void loadData()
}

async function loadOptions() {
  const [roomData, templateList] = await Promise.all([
    listRooms({ page_size: 500 }),
    listRackTemplates(),
  ])
  rooms.value = roomData.items
  templates.value = templateList
}

async function loadData() {
  loading.value = true
  clearRackSelection()
  try {
    const data = await listRacks({
      page: pagination.page,
      page_size: pagination.page_size,
      keyword: keyword.value || undefined,
      room_id: roomFilter.value || undefined,
      sort: rackSort.sort,
      order: rackSort.order,
    })
    tableData.value = data.items
    pagination.total = data.pagination.total
  } finally {
    loading.value = false
  }
}

async function refreshTemplates() {
  templates.value = await listRackTemplates()
}

// —— 样式模板 ——
const templateDialogVisible = ref(false)
const editingTemplateId = ref<string | null>(null)
const templateForm = reactive({
  code: '',
  name: '',
  total_u: 42,
  width: 600,
  depth: 1000,
  description: '',
})

const templatePreviewCode = computed(() => templateForm.code || templateForm.name || '模板预览')

function openCreateTemplate() {
  editingTemplateId.value = null
  templateForm.code = ''
  templateForm.name = ''
  templateForm.total_u = 42
  templateForm.width = 600
  templateForm.depth = 1000
  templateForm.description = ''
  templateDialogVisible.value = true
}

function openEditTemplate(row: RackTemplate) {
  editingTemplateId.value = row.id
  templateForm.code = row.code
  templateForm.name = row.name
  templateForm.total_u = row.total_u
  templateForm.width = row.width
  templateForm.depth = row.depth
  templateForm.description = row.description || ''
  templateDialogVisible.value = true
}

async function submitTemplate() {
  if (!templateForm.code || !templateForm.name) {
    ElMessage.warning('请填写编码和名称')
    return
  }
  if (!templateForm.total_u || templateForm.total_u < 1) {
    ElMessage.warning('请填写有效的 U 位数')
    return
  }
  try {
    if (editingTemplateId.value) {
      await updateRackTemplate(editingTemplateId.value, {
        name: templateForm.name,
        total_u: templateForm.total_u,
        width: templateForm.width,
        depth: templateForm.depth,
        description: templateForm.description || null,
      })
      ElMessage.success('模板已更新')
    } else {
      await createRackTemplate({
        code: templateForm.code,
        name: templateForm.name,
        total_u: templateForm.total_u,
        width: templateForm.width,
        depth: templateForm.depth,
        description: templateForm.description || null,
      })
      ElMessage.success('模板已创建')
    }
    templateDialogVisible.value = false
    await refreshTemplates()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '保存失败')
  }
}

async function handleDeleteTemplate(row: RackTemplate) {
  await ElMessageBox.confirm(`确定删除模板「${row.name}」吗？`, '确认删除', { type: 'warning' })
  await deleteRackTemplate(row.id)
  ElMessage.success('已删除')
  await refreshTemplates()
}

// —— 应用模板到机房 ——
const applyVisible = ref(false)
const applyForm = reactive({
  template_id: '',
  room_id: '',
  fill_empty_slots: true,
})
const applyLoading = ref(false)

const applyTemplate = computed(
  () => templates.value.find((t) => t.id === applyForm.template_id) || null,
)
const applyRoom = computed(() => rooms.value.find((r) => r.id === applyForm.room_id) || null)

function openApply(templateId?: string) {
  applyForm.template_id = templateId || templates.value[0]?.id || ''
  applyForm.room_id = rooms.value[0]?.id || ''
  applyForm.fill_empty_slots = true
  applyVisible.value = true
}

async function submitApply() {
  if (!applyForm.template_id || !applyForm.room_id) {
    ElMessage.warning('请选择模板和机房')
    return
  }
  const tpl = applyTemplate.value
  const room = applyRoom.value
  await ElMessageBox.confirm(
    `将模板「${tpl?.name}」应用到机房「${room ? roomLabel(room) : ''}」？\n` +
      (applyForm.fill_empty_slots
        ? '将更新已有机柜，并为空闲机柜位创建机柜。'
        : '仅更新该机房已有机柜规格。'),
    '应用模板',
    { type: 'warning' },
  )
  applyLoading.value = true
  try {
    const result = await applyTemplateToRoom(
      applyForm.template_id,
      applyForm.room_id,
      applyForm.fill_empty_slots,
    )
    ElMessage.success(
      `完成：更新 ${result.updated}，新建 ${result.created}` +
        (result.skipped ? `，跳过 ${result.skipped}` : ''),
    )
    if (result.errors?.length) {
      ElMessage.warning(result.errors.slice(0, 3).join('；'))
    }
    applyVisible.value = false
    activeTab.value = 'racks'
    roomFilter.value = applyForm.room_id
    pagination.page = 1
    await Promise.all([refreshTemplates(), loadData()])
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '应用失败')
  } finally {
    applyLoading.value = false
  }
}

// —— 取消模板应用到机房 ——
const unapplyVisible = ref(false)
const unapplyLoading = ref(false)
const unapplyForm = reactive({
  template_id: '',
  room_id: '',
  delete_empty_racks: true,
  detach_template: true,
})

const unapplyTemplate = computed(
  () => templates.value.find((t) => t.id === unapplyForm.template_id) || null,
)

const appliedTemplates = computed(() =>
  templates.value.filter((t) => (t.applied_rack_count || 0) > 0 || (t.applied_rooms?.length || 0) > 0),
)

const hasAppliedTemplates = computed(() => appliedTemplates.value.length > 0)

const unapplyRooms = computed(() => unapplyTemplate.value?.applied_rooms || [])

const unapplyRoom = computed(
  () => unapplyRooms.value.find((r) => r.id === unapplyForm.room_id) || null,
)

function isTemplateApplied(row: RackTemplate) {
  return (row.applied_rack_count || 0) > 0 || (row.applied_rooms?.length || 0) > 0
}

function appliedRoomsLabel(row: RackTemplate) {
  if (!isTemplateApplied(row)) return ''
  return (row.applied_rooms || [])
    .map((r) => `${r.name}×${r.rack_count}`)
    .join('、')
}

function syncUnapplyRoom() {
  const rooms = unapplyRooms.value
  if (!rooms.length) {
    unapplyForm.room_id = ''
    return
  }
  if (!rooms.some((r) => r.id === unapplyForm.room_id)) {
    unapplyForm.room_id = rooms[0].id
  }
}

function openUnapply(templateId?: string) {
  const preferred =
    (templateId && templates.value.find((t) => t.id === templateId && isTemplateApplied(t))) ||
    appliedTemplates.value[0]
  if (!preferred) {
    ElMessage.info('当前没有已应用到机房的模板')
    return
  }
  unapplyForm.template_id = preferred.id
  unapplyForm.delete_empty_racks = true
  unapplyForm.detach_template = true
  syncUnapplyRoom()
  unapplyVisible.value = true
}

function onUnapplyTemplateChange() {
  syncUnapplyRoom()
}

async function submitUnapply() {
  if (!unapplyForm.template_id || !unapplyForm.room_id) {
    ElMessage.warning('请选择已应用的模板和机房')
    return
  }
  if (!unapplyRooms.value.some((r) => r.id === unapplyForm.room_id)) {
    ElMessage.warning('所选机房未引用该模板')
    return
  }
  if (!unapplyForm.delete_empty_racks && !unapplyForm.detach_template) {
    ElMessage.warning('请至少勾选一项操作')
    return
  }
  const tpl = unapplyTemplate.value
  const room = unapplyRoom.value
  await ElMessageBox.confirm(
    `取消模板「${tpl?.name}」在机房「${room?.name || ''}」的应用？\n` +
      `该机房当前有 ${room?.rack_count || 0} 台机柜引用此模板。\n` +
      (unapplyForm.delete_empty_racks ? '• 删除绑定该模板且无设备的机柜\n' : '') +
      (unapplyForm.detach_template ? '• 其余机柜解除模板关联（保留实例）' : ''),
    '取消模板应用',
    { type: 'warning' },
  )
  unapplyLoading.value = true
  try {
    const result = await unapplyTemplateFromRoom(unapplyForm.template_id, unapplyForm.room_id, {
      deleteEmptyRacks: unapplyForm.delete_empty_racks,
      detachTemplate: unapplyForm.detach_template,
    })
    ElMessage.success(
      `完成：删除 ${result.deleted}，解除关联 ${result.detached}` +
        (result.skipped ? `，跳过 ${result.skipped}` : ''),
    )
    if (result.errors?.length) {
      ElMessage.warning(result.errors.slice(0, 3).join('；'))
    }
    unapplyVisible.value = false
    activeTab.value = 'racks'
    roomFilter.value = unapplyForm.room_id
    pagination.page = 1
    await Promise.all([refreshTemplates(), loadData()])
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '取消应用失败')
  } finally {
    unapplyLoading.value = false
  }
}

// —— 机柜实例批量操作 ——
async function handleBatchDeleteRacks() {
  if (!selectedRacks.value.length) {
    ElMessage.warning('请先勾选机柜实例')
    return
  }
  await ElMessageBox.confirm(
    `确定批量删除选中的 ${selectedRacks.value.length} 台机柜吗？\n有设备占用的机柜将自动跳过。`,
    '批量删除',
    { type: 'warning' },
  )
  batchDeleting.value = true
  try {
    const result = await batchDeleteRacks(selectedRacks.value.map((r) => r.id))
    ElMessage.success(
      `完成：删除 ${result.deleted}` + (result.skipped ? `，跳过 ${result.skipped}` : ''),
    )
    if (result.errors?.length) {
      ElMessage.warning(result.errors.slice(0, 3).join('；'))
    }
    clearRackSelection()
    await loadData()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '批量删除失败')
  } finally {
    batchDeleting.value = false
  }
}

// —— 放置机柜（整机房 / 按排 / 按列 / 单机柜） ——
const placeVisible = ref(false)
const placeLoading = ref(false)
const placeForm = reactive({
  room_id: '',
  mode: 'all' as 'all' | 'by_row' | 'by_column' | 'single',
  template_id: '',
  fill_empty_slots: true,
  update_existing: true,
  slot_key: '',
  code: '',
  name: '',
})
const roomRacks = ref<Rack[]>([])
const rowTemplateMap = ref<Record<string, string>>({})
const columnTemplateMap = ref<Record<string, string>>({})
const codeCheck = ref<RackCodeCheck | null>(null)
const codeChecking = ref(false)

const placeRoom = computed(() => rooms.value.find((r) => r.id === placeForm.room_id) || null)

const placeRowLayout = computed(() => {
  const room = placeRoom.value
  if (!room) return [] as number[]
  return room.row_layout?.length
    ? room.row_layout
    : Array.from({ length: room.rack_rows }, () => room.rack_columns)
})

const placeColumnCount = computed(() =>
  placeRowLayout.value.length ? Math.max(...placeRowLayout.value) : 0,
)

const placeSlotStats = computed(() => {
  const layout = placeRowLayout.value
  const total = layout.reduce((s, n) => s + n, 0)
  const occupied = roomRacks.value.length
  return { total, occupied, free: Math.max(total - occupied, 0) }
})

const availableSlots = computed(() => {
  const room = placeRoom.value
  if (!room) return []
  const layout = placeRowLayout.value
  const codes = room.slot_codes || []
  const occupied = new Set(roomRacks.value.map((r) => `${r.row_no}-${r.column_no}`))
  const slots: Array<{ key: string; label: string; row_no: number; column_no: number; code: string }> =
    []
  layout.forEach((cols, idx) => {
    const row = idx + 1
    for (let col = 1; col <= cols; col += 1) {
      const key = `${row}-${col}`
      if (!occupied.has(key)) {
        const code =
          codes[idx]?.[col - 1] || `R${String(row).padStart(2, '0')}${String(col).padStart(2, '0')}`
        slots.push({
          key,
          label: `${code}（第 ${row} 排 · 第 ${col} 列）`,
          row_no: row,
          column_no: col,
          code,
        })
      }
    }
  })
  return slots
})

function initRowColumnMaps() {
  const defaultId = placeForm.template_id || templates.value[0]?.id || ''
  const rows: Record<string, string> = {}
  placeRowLayout.value.forEach((_, idx) => {
    rows[String(idx + 1)] = rowTemplateMap.value[String(idx + 1)] || defaultId
  })
  rowTemplateMap.value = rows

  const cols: Record<string, string> = {}
  for (let c = 1; c <= placeColumnCount.value; c += 1) {
    cols[String(c)] = columnTemplateMap.value[String(c)] || defaultId
  }
  columnTemplateMap.value = cols
}

function applyDefaultToAllRows() {
  if (!placeForm.template_id) return
  const next: Record<string, string> = {}
  placeRowLayout.value.forEach((_, idx) => {
    next[String(idx + 1)] = placeForm.template_id
  })
  rowTemplateMap.value = next
}

function applyDefaultToAllColumns() {
  if (!placeForm.template_id) return
  const next: Record<string, string> = {}
  for (let c = 1; c <= placeColumnCount.value; c += 1) {
    next[String(c)] = placeForm.template_id
  }
  columnTemplateMap.value = next
}

async function refreshCodeCheck(code = placeForm.code) {
  if (!code) {
    codeCheck.value = null
    return
  }
  codeChecking.value = true
  try {
    codeCheck.value = await checkRackCode(code, placeForm.room_id || undefined, code)
  } catch {
    codeCheck.value = null
  } finally {
    codeChecking.value = false
  }
}

async function onPlaceRoomChange(roomId: string) {
  if (!roomId) {
    roomRacks.value = []
    placeForm.slot_key = ''
    codeCheck.value = null
    return
  }
  const data = await listRacks({ room_id: roomId, page_size: 500 })
  roomRacks.value = data.items
  initRowColumnMaps()
  placeForm.slot_key = availableSlots.value[0]?.key || ''
  if (placeForm.mode === 'single' && placeForm.slot_key) {
    await applyPlaceSlot(placeForm.slot_key)
  }
}

async function applyPlaceSlot(slotKey: string) {
  const slot = availableSlots.value.find((s) => s.key === slotKey)
  if (!slot) return
  placeForm.code = slot.code
  placeForm.name = slot.code
  await refreshCodeCheck(slot.code)
}

function onPlaceModeChange() {
  if (placeForm.mode === 'by_row') applyDefaultToAllRows()
  if (placeForm.mode === 'by_column') applyDefaultToAllColumns()
  if (placeForm.mode === 'single' && placeForm.slot_key) void applyPlaceSlot(placeForm.slot_key)
}

function openPlace() {
  placeForm.room_id = rooms.value[0]?.id || ''
  placeForm.mode = 'all'
  placeForm.template_id = templates.value[0]?.id || ''
  placeForm.fill_empty_slots = true
  placeForm.update_existing = true
  placeForm.code = ''
  placeForm.name = ''
  codeCheck.value = null
  rowTemplateMap.value = {}
  columnTemplateMap.value = {}
  placeVisible.value = true
  if (placeForm.room_id) void onPlaceRoomChange(placeForm.room_id)
}

async function submitPlace() {
  if (!placeForm.room_id) {
    ElMessage.warning('请选择机房')
    return
  }
  if (placeForm.mode === 'all' && !placeForm.template_id) {
    ElMessage.warning('请选择机柜样式模板')
    return
  }
  if (placeForm.mode === 'by_row') {
    const missing = placeRowLayout.value.some((_, i) => !rowTemplateMap.value[String(i + 1)])
    if (missing && !placeForm.template_id) {
      ElMessage.warning('请为每一排指定模板，或设置默认模板')
      return
    }
  }
  if (placeForm.mode === 'by_column') {
    const missing = Array.from({ length: placeColumnCount.value }, (_, i) => i + 1).some(
      (c) => !columnTemplateMap.value[String(c)],
    )
    if (missing && !placeForm.template_id) {
      ElMessage.warning('请为每一列指定模板，或设置默认模板')
      return
    }
  }
  if (placeForm.mode === 'single') {
    if (!placeForm.slot_key || !placeForm.template_id) {
      ElMessage.warning('请选择机柜位和模板')
      return
    }
    const slot = availableSlots.value.find((s) => s.key === placeForm.slot_key)
    if (!slot) {
      ElMessage.warning('请选择有效的机柜位')
      return
    }
    placeForm.code = slot.code
    placeForm.name = slot.code
  }

  const modeLabel =
    placeForm.mode === 'all'
      ? '整机房'
      : placeForm.mode === 'by_row'
        ? '按排'
        : placeForm.mode === 'by_column'
          ? '按列'
          : '单机柜位'
  await ElMessageBox.confirm(
    `确认按「${modeLabel}」模式放置/套用模板到所选机房？\n` +
      `机柜位 ${placeSlotStats.value.total}（已有 ${placeSlotStats.value.occupied}，空闲 ${placeSlotStats.value.free}）`,
    '确认放置',
    { type: 'warning' },
  )

  placeLoading.value = true
  try {
    const slot = availableSlots.value.find((s) => s.key === placeForm.slot_key)
    const result = await placeRacksBatch({
      room_id: placeForm.room_id,
      mode: placeForm.mode,
      template_id: placeForm.template_id || undefined,
      row_templates: placeForm.mode === 'by_row' ? { ...rowTemplateMap.value } : undefined,
      column_templates: placeForm.mode === 'by_column' ? { ...columnTemplateMap.value } : undefined,
      fill_empty_slots: placeForm.fill_empty_slots,
      update_existing: placeForm.update_existing,
      row_no: placeForm.mode === 'single' ? slot?.row_no : undefined,
      column_no: placeForm.mode === 'single' ? slot?.column_no : undefined,
      code: placeForm.mode === 'single' ? placeForm.code : undefined,
      name: placeForm.mode === 'single' ? placeForm.name : undefined,
    })
    ElMessage.success(
      `完成：更新 ${result.updated}，新建 ${result.created}` +
        (result.skipped ? `，跳过 ${result.skipped}` : ''),
    )
    if (result.errors?.length) {
      ElMessage.warning(result.errors.slice(0, 3).join('；'))
    }
    placeVisible.value = false
    activeTab.value = 'racks'
    roomFilter.value = placeForm.room_id
    pagination.page = 1
    await Promise.all([refreshTemplates(), loadData()])
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '放置失败')
  } finally {
    placeLoading.value = false
  }
}

// —— 编辑机柜实例 ——
const editVisible = ref(false)
const editingRackId = ref<string | null>(null)
const editForm = reactive({ name: '', total_u: 42, status: 'active', description: '' })

function openEditRack(row: Rack) {
  editingRackId.value = row.id
  editForm.name = row.name
  editForm.total_u = row.total_u
  editForm.status = row.status
  editForm.description = row.description || ''
  editVisible.value = true
}

async function submitEditRack() {
  if (!editingRackId.value || !editForm.name) {
    ElMessage.warning('请填写名称')
    return
  }
  try {
    await updateRack(editingRackId.value, {
      name: editForm.name,
      total_u: editForm.total_u,
      status: editForm.status,
      description: editForm.description || null,
    })
    ElMessage.success('已更新')
    editVisible.value = false
    await loadData()
  } catch {
    ElMessage.error('更新失败')
  }
}

async function openLayout(row: Rack) {
  layoutLoading.value = true
  layoutVisible.value = true
  try {
    const data = await getRackLayout(row.id)
    layoutRack.value = data.rack
    layoutSlots.value = data.slots || []
    layoutTotalPower.value = data.total_power || 0
  } catch {
    layoutVisible.value = false
    ElMessage.error('加载机柜布局失败')
  } finally {
    layoutLoading.value = false
  }
}

async function exportSvg() {
  if (!layoutRack.value) return
  exportLoading.value = true
  try {
    const resp = await fetch(`/api/v1/racks/${layoutRack.value.id}/svg`, {
      headers: { Authorization: `Bearer ${auth.accessToken}` },
    })
    if (!resp.ok) {
      ElMessage.error('导出失败')
      return
    }
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${layoutRack.value.code || 'rack'}.svg`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('已导出 SVG')
  } catch {
    ElMessage.error('导出失败')
  } finally {
    exportLoading.value = false
  }
}

async function handleDeleteRack(row: Rack) {
  await ElMessageBox.confirm(`确定删除机柜「${row.name}」吗？`, '确认删除', { type: 'warning' })
  await deleteRack(row.id)
  ElMessage.success('删除成功')
  await loadData()
}

onMounted(() => {
  void Promise.all([loadOptions(), loadData()])
})
</script>

<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>机柜管理</span>
          <div class="actions">
            <el-button v-if="canCreate" type="primary" @click="openCreateTemplate">新建模板</el-button>
            <el-button v-if="canUpdate" @click="openApply()">应用模板到机房</el-button>
            <el-button
              v-if="canUpdate"
              :disabled="!hasAppliedTemplates"
              @click="openUnapply()"
            >
              取消模板应用到机房
            </el-button>
            <el-button v-if="canCreate" @click="openPlace">放置机柜</el-button>
          </div>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="样式模板" name="templates">
          <el-table :data="templates" stripe>
            <el-table-column prop="code" label="编码" width="140" />
            <el-table-column prop="name" label="名称" min-width="140" />
            <el-table-column prop="total_u" label="U 位" width="80" />
            <el-table-column label="尺寸" width="140">
              <template #default="{ row }">{{ row.width }}×{{ row.depth }} mm</template>
            </el-table-column>
            <el-table-column label="已应用机房" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="isTemplateApplied(row)">{{ appliedRoomsLabel(row) }}</span>
                <span v-else class="muted">未应用</span>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" min-width="140" show-overflow-tooltip />
            <el-table-column label="操作" width="280" fixed="right">
              <template #default="{ row }">
                <el-button v-if="canUpdate" type="primary" link @click="openApply(row.id)">应用到机房</el-button>
                <el-button
                  v-if="canUpdate"
                  type="warning"
                  link
                  :disabled="!isTemplateApplied(row)"
                  @click="openUnapply(row.id)"
                >
                  取消应用
                </el-button>
                <el-button v-if="canUpdate" type="primary" link @click="openEditTemplate(row)">编辑</el-button>
                <el-button v-if="canDelete" type="danger" link @click="handleDeleteTemplate(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="机柜实例" name="racks">
          <div class="rack-filters">
            <el-select
              v-model="roomFilter"
              clearable
              placeholder="筛选机房"
              style="width: 200px"
              @change="loadData"
            >
              <el-option v-for="room in rooms" :key="room.id" :label="roomLabel(room)" :value="room.id" />
            </el-select>
            <el-input
              v-model="keyword"
              placeholder="搜索编码/名称"
              clearable
              style="width: 200px"
              @keyup.enter="loadData"
              @clear="loadData"
            />
            <el-button @click="loadData">搜索</el-button>
            <div v-if="canDelete" class="batch-actions">
              <span v-if="selectedRacks.length" class="batch-hint">已选 {{ selectedRacks.length }} 台</span>
              <el-button
                type="danger"
                plain
                :disabled="!selectedRacks.length"
                :loading="batchDeleting"
                @click="handleBatchDeleteRacks"
              >
                批量删除
              </el-button>
            </div>
          </div>

          <el-table
            ref="rackTableRef"
            v-loading="loading"
            :data="tableData"
            stripe
            row-key="id"
            :default-sort="{ prop: 'code', order: 'ascending' }"
            @selection-change="onRackSelectionChange"
            @sort-change="onRackSortChange"
          >
            <el-table-column type="selection" width="48" />
            <el-table-column prop="code" label="机柜编号" width="140" sortable="custom" />
            <el-table-column prop="name" label="名称" min-width="120" />
            <el-table-column label="机房" min-width="120">
              <template #default="{ row }">{{ roomName(row.room_id) }}</template>
            </el-table-column>
            <el-table-column label="样式模板" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ templateName(row.rack_template_id) }}</template>
            </el-table-column>
            <el-table-column label="位置" width="100">
              <template #default="{ row }">R{{ row.row_no }}-C{{ row.column_no }}</template>
            </el-table-column>
            <el-table-column prop="total_u" label="U位" width="70" />
            <el-table-column label="利用率" width="100">
              <template #default="{ row }">{{ row.utilization }}%</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="openLayout(row)">机柜图</el-button>
                <el-button v-if="canUpdate" type="primary" link @click="openEditRack(row)">编辑</el-button>
                <el-button v-if="canDelete" type="danger" link @click="handleDeleteRack(row)">删除</el-button>
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
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新建/编辑样式模板（不关联机房） -->
    <el-dialog
      v-model="templateDialogVisible"
      :title="editingTemplateId ? '编辑机柜样式模板' : '新建机柜样式模板'"
      width="960px"
      destroy-on-close
    >
      <div class="create-layout">
        <div class="create-form">
          <el-form label-width="90px">
            <el-form-item label="编码" required>
              <el-input v-model="templateForm.code" :disabled="!!editingTemplateId" placeholder="如 STD-42U" />
            </el-form-item>
            <el-form-item label="名称" required>
              <el-input v-model="templateForm.name" placeholder="模板显示名称" />
            </el-form-item>
            <el-form-item label="U 位数" required>
              <el-input-number v-model="templateForm.total_u" :min="1" :max="60" style="width: 100%" />
            </el-form-item>
            <el-form-item label="宽度 mm">
              <el-input-number v-model="templateForm.width" :min="400" :max="1200" style="width: 100%" />
            </el-form-item>
            <el-form-item label="深度 mm">
              <el-input-number v-model="templateForm.depth" :min="600" :max="1500" style="width: 100%" />
            </el-form-item>
            <el-form-item label="设备统计">
              <div class="device-stats">
                <div class="stat-card primary">
                  <div class="stat-value">0</div>
                  <div class="stat-label">设备数（台）</div>
                </div>
                <div class="stat-card">
                  <div class="stat-value">0<span class="unit">/{{ templateForm.total_u }}U</span></div>
                  <div class="stat-label">已用 U 位</div>
                </div>
                <div class="stat-card">
                  <div class="stat-value">{{ templateForm.total_u }}<span class="unit">U</span></div>
                  <div class="stat-label">空闲 U 位</div>
                </div>
                <div class="stat-card">
                  <div class="stat-value">0<span class="unit">%</span></div>
                  <div class="stat-label">利用率</div>
                </div>
                <div class="stats-hint">模板本身无设备；应用到机房后按实例统计</div>
              </div>
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="templateForm.description" type="textarea" :rows="2" />
            </el-form-item>
          </el-form>
        </div>
        <div class="create-preview">
          <div class="preview-title">样式预览</div>
          <RackCabinet :code="templatePreviewCode" :total-u="templateForm.total_u" :total-power="0" compact />
        </div>
      </div>
      <template #footer>
        <el-button @click="templateDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTemplate">保存模板</el-button>
      </template>
    </el-dialog>

    <!-- 应用模板到机房 -->
    <el-dialog v-model="applyVisible" title="应用模板到机房" width="520px">
      <el-form label-width="110px">
        <el-form-item label="样式模板" required>
          <el-select v-model="applyForm.template_id" style="width: 100%">
            <el-option
              v-for="t in templates"
              :key="t.id"
              :label="`${t.name}（${t.total_u}U）`"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="目标机房" required>
          <el-select v-model="applyForm.room_id" style="width: 100%" filterable>
            <el-option v-for="room in rooms" :key="room.id" :label="roomLabel(room)" :value="room.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="空闲位">
          <el-checkbox v-model="applyForm.fill_empty_slots">为空闲机柜位创建机柜并套用模板</el-checkbox>
          <div class="field-hint">开启后：更新已有机柜规格，并按机房布局补齐全部机柜位</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="applyVisible = false">取消</el-button>
        <el-button type="primary" :loading="applyLoading" @click="submitApply">开始应用</el-button>
      </template>
    </el-dialog>

    <!-- 取消模板应用到机房 -->
    <el-dialog v-model="unapplyVisible" title="取消模板应用到机房" width="560px">
      <el-form label-width="110px">
        <el-form-item label="样式模板" required>
          <el-select
            v-model="unapplyForm.template_id"
            style="width: 100%"
            :disabled="!appliedTemplates.length"
            @change="onUnapplyTemplateChange"
          >
            <el-option
              v-for="t in appliedTemplates"
              :key="t.id"
              :label="`${t.name}（${t.applied_rack_count || 0} 台 / ${(t.applied_rooms || []).length} 机房）`"
              :value="t.id"
            />
          </el-select>
          <div v-if="!appliedTemplates.length" class="field-hint">暂无已应用到机房的模板</div>
        </el-form-item>
        <el-form-item label="关联机房" required>
          <el-select
            v-model="unapplyForm.room_id"
            style="width: 100%"
            filterable
            :disabled="!unapplyRooms.length"
            placeholder="仅显示已引用该模板的机房"
          >
            <el-option
              v-for="room in unapplyRooms"
              :key="room.id"
              :label="`${room.name}（${room.rack_count} 台）`"
              :value="room.id"
            />
          </el-select>
          <div v-if="unapplyRoom?.room_deleted" class="field-hint warn-hint">
            该机房已删除，但仍有机柜引用此模板；确认后可清理这些残留关联
          </div>
          <div v-if="unapplyTemplate && !unapplyRooms.length" class="field-hint">
            该模板当前没有关联机房
          </div>
        </el-form-item>
        <el-form-item label="处理方式">
          <el-checkbox v-model="unapplyForm.delete_empty_racks">
            删除绑定该模板且无设备的机柜
          </el-checkbox>
          <el-checkbox v-model="unapplyForm.detach_template">
            对其余机柜解除模板关联（保留机柜实例与规格）
          </el-checkbox>
          <div class="field-hint">仅影响所选机房中仍绑定该模板的机柜实例</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="unapplyVisible = false">关闭</el-button>
        <el-button
          type="warning"
          :loading="unapplyLoading"
          :disabled="!unapplyForm.template_id || !unapplyForm.room_id"
          @click="submitUnapply"
        >
          确认取消应用
        </el-button>
      </template>
    </el-dialog>

    <!-- 放置机柜：整机房 / 按排 / 按列 / 单机柜 -->
    <el-dialog v-model="placeVisible" title="放置机柜" width="720px" destroy-on-close>
      <el-form label-width="110px">
        <el-form-item label="目标机房" required>
          <el-select v-model="placeForm.room_id" style="width: 100%" filterable @change="onPlaceRoomChange">
            <el-option v-for="room in rooms" :key="room.id" :label="roomLabel(room)" :value="room.id" />
          </el-select>
          <div v-if="placeRoom" class="field-hint">
            布局 {{ placeRowLayout.length }} 排，机柜位 {{ placeSlotStats.total }}
            （已有 {{ placeSlotStats.occupied }}，空闲 {{ placeSlotStats.free }}）
          </div>
        </el-form-item>

        <el-form-item label="放置范围" required>
          <el-radio-group v-model="placeForm.mode" @change="onPlaceModeChange">
            <el-radio-button value="all">整机房</el-radio-button>
            <el-radio-button value="by_row">按排自定义</el-radio-button>
            <el-radio-button value="by_column">按列自定义</el-radio-button>
            <el-radio-button value="single">单机柜位</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item
          v-if="placeForm.mode === 'all' || placeForm.mode === 'single' || placeForm.mode === 'by_row' || placeForm.mode === 'by_column'"
          :label="placeForm.mode === 'all' || placeForm.mode === 'single' ? '样式模板' : '默认模板'"
          :required="placeForm.mode === 'all' || placeForm.mode === 'single'"
        >
          <el-select
            v-model="placeForm.template_id"
            style="width: 100%"
            @change="() => { if (placeForm.mode === 'by_row') applyDefaultToAllRows(); if (placeForm.mode === 'by_column') applyDefaultToAllColumns() }"
          >
            <el-option
              v-for="t in templates"
              :key="t.id"
              :label="`${t.name}（${t.total_u}U）`"
              :value="t.id"
            />
          </el-select>
          <div v-if="placeForm.mode === 'all'" class="field-hint">所选机房内全部机柜将套用该模板</div>
          <div v-else-if="placeForm.mode !== 'single'" class="field-hint">未单独指定的排/列将使用此默认模板</div>
        </el-form-item>

        <el-form-item v-if="placeForm.mode === 'by_row'" label="各排模板">
          <div class="map-table">
            <div class="map-toolbar">
              <el-button size="small" @click="applyDefaultToAllRows">全部填入默认模板</el-button>
            </div>
            <div v-for="(cols, idx) in placeRowLayout" :key="idx" class="map-row">
              <span class="map-label">第 {{ idx + 1 }} 排（{{ cols }} 柜）</span>
              <el-select v-model="rowTemplateMap[String(idx + 1)]" style="flex: 1" placeholder="选择模板">
                <el-option
                  v-for="t in templates"
                  :key="t.id"
                  :label="`${t.name}（${t.total_u}U）`"
                  :value="t.id"
                />
              </el-select>
            </div>
          </div>
        </el-form-item>

        <el-form-item v-if="placeForm.mode === 'by_column'" label="各列模板">
          <div class="map-table">
            <div class="map-toolbar">
              <el-button size="small" @click="applyDefaultToAllColumns">全部填入默认模板</el-button>
            </div>
            <div v-for="c in placeColumnCount" :key="c" class="map-row">
              <span class="map-label">第 {{ c }} 列</span>
              <el-select v-model="columnTemplateMap[String(c)]" style="flex: 1" placeholder="选择模板">
                <el-option
                  v-for="t in templates"
                  :key="t.id"
                  :label="`${t.name}（${t.total_u}U）`"
                  :value="t.id"
                />
              </el-select>
            </div>
          </div>
        </el-form-item>

        <template v-if="placeForm.mode === 'single'">
          <el-form-item label="机柜位" required>
            <el-select v-model="placeForm.slot_key" style="width: 100%" @change="applyPlaceSlot">
              <el-option v-for="slot in availableSlots" :key="slot.key" :label="slot.label" :value="slot.key" />
            </el-select>
            <div v-if="!availableSlots.length" class="field-hint warn">该机房空闲机柜位已满</div>
          </el-form-item>
          <el-form-item label="机柜编号">
            <el-input :model-value="placeForm.code" disabled />
            <div class="field-hint">使用机房布局中的机柜编号，编码与名称相同</div>
          </el-form-item>
        </template>

        <el-form-item v-if="placeForm.mode !== 'single'" label="选项">
          <el-checkbox v-model="placeForm.update_existing">更新已有机柜规格</el-checkbox>
          <el-checkbox v-model="placeForm.fill_empty_slots">为空闲机柜位创建机柜</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="placeVisible = false">取消</el-button>
        <el-button type="primary" :loading="placeLoading" @click="submitPlace">开始放置</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑机柜" width="480px">
      <el-form label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="U 位数">
          <el-input-number v-model="editForm.total_u" :min="1" :max="60" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" style="width: 100%">
            <el-option v-for="opt in statusOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEditRack">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="layoutVisible"
      :title="`机柜图 - ${layoutRack?.code || ''}`"
      size="480px"
    >
      <div v-loading="layoutLoading" class="layout-panel">
        <div v-if="layoutRack" class="layout-toolbar">
          <div class="layout-meta">
            <span>编号 {{ layoutRack.code }}</span>
            <span>已用 {{ layoutRack.occupied_u }}/{{ layoutRack.total_u }}U</span>
            <span>利用率 {{ layoutRack.utilization }}%</span>
          </div>
          <el-button size="small" :loading="exportLoading" @click="exportSvg">导出 SVG</el-button>
        </div>
        <RackCabinet
          v-if="layoutRack"
          :code="layoutRack.code"
          :total-u="layoutRack.total_u"
          :slots="layoutSlots"
          :total-power="layoutTotalPower"
        />
      </div>
    </el-drawer>
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

.actions,
.rack-filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.rack-filters {
  margin-bottom: 12px;
}

.batch-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.batch-hint {
  font-size: 13px;
  color: #606266;
}

.muted {
  color: #c0c4cc;
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

.warn-hint {
  color: #e6a23c;
}

.field-hint.warn {
  color: #e6a23c;
}

.field-hint.ok {
  color: #67c23a;
}

.map-table {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.map-toolbar {
  margin-bottom: 4px;
}

.map-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.map-label {
  width: 120px;
  flex-shrink: 0;
  font-size: 13px;
  color: #606266;
}

.create-layout {
  display: grid;
  grid-template-columns: minmax(320px, 1fr) minmax(340px, 400px);
  gap: 20px;
  align-items: start;
}

.preview-title {
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 600;
  color: #606266;
}

.device-stats {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.stat-card {
  padding: 10px 12px;
  border-radius: 8px;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
}

.stat-card.primary {
  background: linear-gradient(135deg, #1f2a3a, #2c3e50);
  border-color: #1f2a3a;
  color: #fff;
}

.stat-card.primary .stat-label {
  color: rgba(255, 255, 255, 0.7);
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.stat-value .unit {
  margin-left: 2px;
  font-size: 12px;
  font-weight: 500;
  opacity: 0.75;
}

.stat-label {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}

.stats-hint {
  grid-column: 1 / -1;
  font-size: 12px;
  color: #909399;
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

@media (max-width: 900px) {
  .create-layout {
    grid-template-columns: 1fr;
  }
}
</style>
