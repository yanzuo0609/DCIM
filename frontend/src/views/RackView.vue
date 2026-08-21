<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  applyTemplateToRoom,
  createRackTemplate,
  deleteRackTemplate,
  listRackTemplates,
  updateRackTemplate,
  type RackTemplate,
  type RackVisualStyle,
} from '@/api/rack'
import { listRooms, type Room } from '@/api/room'
import { useAuthStore } from '@/stores/auth'
import RackCabinet from '@/components/RackCabinet.vue'

const VISUAL_STYLE_OPTIONS: Array<{
  value: RackVisualStyle
  label: string
  hint: string
}> = [
  { value: 'classic', label: '经典立面', hint: '原深色机柜立面（默认）' },
  { value: 'schematic', label: '线框立面', hint: '双侧 U 位刻度，浅色信息列' },
  { value: 'realistic', label: '正面面板', hint: '设备正面面板示意' },
  { value: 'grid', label: '表格占位', hint: '黄格占用、白格空闲' },
]

/** 样式缩略图固定 8U 示意，不随模板 U 数变化 */
const STYLE_THUMB_SLOTS = (() => {
  const total = 8
  type Dev = {
    device_id: string
    hostname: string
    height_u: number
    start_u: number
    power: number
    ip_summary: string | null
    bmc_ip?: string | null
    model_name: string
  }
  const byU = new Map<
    number,
    {
      u_position: number
      occupied: boolean
      is_span_start: boolean
      span_height: number
      device: Dev | null
    }
  >()
  const place = (topU: number, height: number, device: Dev) => {
    for (let i = 0; i < height; i += 1) {
      const u = topU - i
      byU.set(u, {
        u_position: u,
        occupied: true,
        is_span_start: i === 0,
        span_height: height,
        device: { ...device, height_u: height, start_u: topU - height + 1 },
      })
    }
  }
  place(8, 2, {
    device_id: 't-2u',
    hostname: 'SRV',
    height_u: 2,
    start_u: 7,
    power: 120,
    ip_summary: '10.0.0.1',
    bmc_ip: '10.0.1.1',
    model_name: '2U',
  })
  place(4, 1, {
    device_id: 't-1u',
    hostname: 'SW',
    height_u: 1,
    start_u: 4,
    power: 40,
    ip_summary: '10.0.0.2',
    model_name: '1U',
  })
  const slots = []
  for (let u = total; u >= 1; u -= 1) {
    slots.push(
      byU.get(u) || {
        u_position: u,
        occupied: false,
        is_span_start: false,
        span_height: 1,
        device: null,
      },
    )
  }
  return slots
})()

const auth = useAuthStore()
const templates = ref<RackTemplate[]>([])
const rooms = ref<Room[]>([])
const selectedRows = ref<RackTemplate[]>([])
const detailVisible = ref(false)
const detailRow = ref<RackTemplate | null>(null)

const canCreate = auth.hasPermission('rack:create')
const canUpdate = auth.hasPermission('rack:update')
const canDelete = auth.hasPermission('rack:delete')

const applyVisible = ref(false)
const applyLoading = ref(false)
const applyLockTemplate = ref(false)
const applyForm = reactive({
  template_id: '',
  room_ids: [] as string[],
  fill_empty_slots: true,
  visual_style: 'classic' as RackVisualStyle,
})

const applyTemplate = computed(
  () => templates.value.find((t) => t.id === applyForm.template_id) || null,
)

function normalizeVisualStyle(value?: string | null): RackVisualStyle {
  if (
    value === 'realistic' ||
    value === 'grid' ||
    value === 'schematic' ||
    value === 'classic'
  ) {
    return value
  }
  return 'classic'
}

watch(
  () => applyForm.template_id,
  (id) => {
    if (!id) return
    const tpl = templates.value.find((t) => t.id === id)
    if (tpl) applyForm.visual_style = normalizeVisualStyle(tpl.visual_style)
  },
)

const selectedApplyRooms = computed(() =>
  rooms.value.filter((r) => applyForm.room_ids.includes(r.id)),
)

const templateDialogVisible = ref(false)
const editingTemplateId = ref<string | null>(null)
const templateForm = reactive({
  code: '',
  name: '',
  total_u: 42,
  width: 600,
  depth: 1000,
  visual_style: 'classic' as RackVisualStyle,
  description: '',
})

const templatePreviewCode = computed(() => templateForm.code || templateForm.name || '预览')

/** 预览用示意占用：含 2U / 4U 合并，便于对照经典立面效果 */
const templatePreviewSlots = computed(() => {
  const total = Math.max(8, templateForm.total_u || 42)
  type PreviewDevice = {
    device_id: string
    hostname: string
    height_u: number
    start_u: number
    power: number
    ip_summary: string | null
    bmc_ip?: string | null
    model_name: string
  }
  const byU = new Map<
    number,
    {
      u_position: number
      occupied: boolean
      is_span_start: boolean
      span_height: number
      device: PreviewDevice | null
    }
  >()

  const place = (topU: number, height: number, device: PreviewDevice) => {
    const h = Math.min(height, topU)
    for (let i = 0; i < h; i += 1) {
      const u = topU - i
      byU.set(u, {
        u_position: u,
        occupied: true,
        is_span_start: i === 0,
        span_height: h,
        device: { ...device, height_u: h, start_u: topU - h + 1 },
      })
    }
  }

  place(total, 2, {
    device_id: 'preview-2u',
    hostname: 'SRV-2U',
    height_u: 2,
    start_u: total - 1,
    power: 200,
    ip_summary: '10.0.0.10',
    bmc_ip: '10.0.1.10',
    model_name: 'Demo-2U',
  })

  const midTop = Math.max(5, Math.floor(total * 0.55))
  if (midTop <= total - 2 && midTop - 3 >= 1) {
    place(midTop, 4, {
      device_id: 'preview-4u',
      hostname: 'SRV-4U',
      height_u: 4,
      start_u: midTop - 3,
      power: 450,
      ip_summary: '10.0.0.40',
      bmc_ip: '10.0.1.40',
      model_name: 'Demo-4U',
    })
  }

  const swU = Math.max(1, Math.floor(total * 0.25))
  if (!byU.has(swU)) {
    place(swU, 1, {
      device_id: 'preview-1u',
      hostname: '交换机',
      height_u: 1,
      start_u: swU,
      power: 80,
      ip_summary: '10.0.0.2',
      bmc_ip: null,
      model_name: 'SW',
    })
  }

  const slots = []
  for (let u = total; u >= 1; u -= 1) {
    slots.push(
      byU.get(u) || {
        u_position: u,
        occupied: false,
        is_span_start: false,
        span_height: 1,
        device: null,
      },
    )
  }
  return slots
})

function visualStyleLabel(value?: string | null) {
  return VISUAL_STYLE_OPTIONS.find((o) => o.value === value)?.label || value || '经典立面'
}

function isTemplateApplied(row: RackTemplate) {
  return (row.applied_rack_count || 0) > 0 || (row.applied_rooms?.length || 0) > 0
}

function appliedRoomsLabel(row: RackTemplate) {
  if (!isTemplateApplied(row)) return ''
  return (row.applied_rooms || [])
    .map((r) => `${r.name}×${r.rack_count}`)
    .join('、')
}

async function refreshTemplates() {
  templates.value = await listRackTemplates()
}

async function loadRooms() {
  const data = await listRooms({ page_size: 500 })
  rooms.value = data.items
}

function roomLabel(room: Room) {
  const parts = [room.location, room.building_no, room.room_no || room.name].filter(Boolean)
  return parts.length ? parts.join('-') : room.name
}

function openApply(templateId?: string) {
  applyForm.template_id = templateId || templates.value[0]?.id || ''
  applyForm.room_ids = []
  applyForm.fill_empty_slots = true
  const tpl = templates.value.find((t) => t.id === applyForm.template_id)
  applyForm.visual_style = normalizeVisualStyle(tpl?.visual_style)
  applyLockTemplate.value = !!templateId
  applyVisible.value = true
}

async function submitApply() {
  if (!applyForm.template_id) {
    ElMessage.warning('请选择样式模板')
    return
  }
  if (!applyForm.room_ids.length) {
    ElMessage.warning('请至少选择一个机房')
    return
  }
  const tpl = applyTemplate.value
  const roomLabels = selectedApplyRooms.value.map((r) => roomLabel(r)).join('、')
  await ElMessageBox.confirm(
    `将模板「${tpl?.name}」以「${visualStyleLabel(applyForm.visual_style)}」样式应用到 ${applyForm.room_ids.length} 个机房？\n${roomLabels}\n` +
      (applyForm.fill_empty_slots
        ? '将更新已有机柜，并为空闲机柜位创建机柜。'
        : '仅更新各机房已有机柜规格。'),
    '应用模板到机房',
    { type: 'warning' },
  )
  applyLoading.value = true
  let updated = 0
  let created = 0
  let skipped = 0
  const errors: string[] = []
  const failedRooms: string[] = []
  try {
    for (const roomId of applyForm.room_ids) {
      const room = rooms.value.find((r) => r.id === roomId)
      const label = room ? roomLabel(room) : roomId
      try {
        const result = await applyTemplateToRoom(
          applyForm.template_id,
          roomId,
          applyForm.fill_empty_slots,
          applyForm.visual_style,
        )
        updated += result.updated
        created += result.created
        skipped += result.skipped
        if (result.errors?.length) {
          errors.push(...result.errors.map((e) => `${label}: ${e}`))
        }
      } catch (error: unknown) {
        failedRooms.push(label)
        const err = error as { response?: { data?: { message?: string } }; message?: string }
        errors.push(`${label}: ${err.response?.data?.message || err.message || '应用失败'}`)
      }
    }
    if (failedRooms.length === applyForm.room_ids.length) {
      ElMessage.error('全部机房应用失败')
    } else {
      ElMessage.success(
        `完成 ${applyForm.room_ids.length - failedRooms.length}/${applyForm.room_ids.length} 个机房：` +
          `更新 ${updated}，新建 ${created}` +
          (skipped ? `，跳过 ${skipped}` : ''),
      )
    }
    if (errors.length) {
      ElMessage.warning(errors.slice(0, 5).join('；'))
    }
    if (!failedRooms.length) {
      applyVisible.value = false
    }
    await refreshTemplates()
  } finally {
    applyLoading.value = false
  }
}

function openCreateTemplate() {
  editingTemplateId.value = null
  templateForm.code = ''
  templateForm.name = ''
  templateForm.total_u = 42
  templateForm.width = 600
  templateForm.depth = 1000
  templateForm.visual_style = 'classic'
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
  templateForm.visual_style =
    row.visual_style === 'realistic' ||
    row.visual_style === 'grid' ||
    row.visual_style === 'schematic' ||
    row.visual_style === 'classic'
      ? (row.visual_style as RackVisualStyle)
      : 'classic'
  templateForm.description = row.description || ''
  templateDialogVisible.value = true
}

async function submitTemplate() {
  if (!templateForm.code || !templateForm.name) {
    ElMessage.warning('请填写编号和名称')
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
        visual_style: templateForm.visual_style,
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
        visual_style: templateForm.visual_style,
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

function rowIndex(index: number) {
  return index + 1
}

function openDetail(row: RackTemplate) {
  detailRow.value = row
  detailVisible.value = true
}

function templateDetailFields(row: RackTemplate) {
  return [
    { label: '名称', value: row.name },
    { label: '编号', value: row.code || '—' },
    { label: '唯一 ID', value: row.id },
    { label: 'U 位', value: String(row.total_u) },
    { label: '视觉样式', value: visualStyleLabel(row.visual_style) },
    { label: '尺寸', value: `${row.width}×${row.depth} mm` },
    {
      label: '已应用机房',
      value: isTemplateApplied(row) ? appliedRoomsLabel(row) : '未应用',
    },
    { label: '描述', value: row.description || '—' },
  ]
}

onMounted(() => {
  void Promise.all([refreshTemplates(), loadRooms()])
})
</script>

<template>
  <div class="page">
    <section class="hero">
      <div class="hero-copy">
        <h2>机柜模板管理</h2>
        <p>维护机柜外观与 U 位规格，可批量应用到单个或多个机房。</p>
      </div>
      <div class="hero-actions">
        <el-button @click="$router.push('/datacenters')">数据中心管理</el-button>
        <el-button @click="$router.push('/rooms/manage')">中心机房管理</el-button>
        <el-button @click="$router.push('/rooms/simulate')">机房3D仿真</el-button>
      </div>
    </section>

    <el-card shadow="never" class="list-card">
      <template #header>
        <div class="card-header">
          <span>机柜模板列表</span>
          <div class="actions">
            <el-button v-if="canUpdate" @click="openApply()">应用到机房</el-button>
            <el-button v-if="canCreate" type="primary" @click="openCreateTemplate">新建模板</el-button>
          </div>
        </div>
      </template>

      <el-table
        :data="templates"
        stripe
        row-key="id"
        @selection-change="(rows: RackTemplate[]) => (selectedRows = rows)"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column label="序号" width="72" align="center">
          <template #default="{ $index }">{{ rowIndex($index) }}</template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="code" label="编号" width="140" />
        <el-table-column label="唯一 ID" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono-id">{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="total_u" label="U 位" width="80" />
        <el-table-column label="视觉样式" width="110">
          <template #default="{ row }">{{ visualStyleLabel(row.visual_style) }}</template>
        </el-table-column>
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
        <el-table-column label="操作" width="88" fixed="right" align="center">
          <template #default="{ row }">
            <el-dropdown trigger="click">
              <el-button type="primary" link>操作</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="openDetail(row)">查看详细信息</el-dropdown-item>
                  <el-dropdown-item v-if="canUpdate" @click="openApply(row.id)">应用到机房</el-dropdown-item>
                  <el-dropdown-item v-if="canUpdate" @click="openEditTemplate(row)">编辑</el-dropdown-item>
                  <el-dropdown-item v-if="canDelete" divided @click="handleDeleteTemplate(row)">
                    删除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="detailVisible" title="模板详细信息" width="560px">
      <el-descriptions v-if="detailRow" :column="1" border>
        <el-descriptions-item
          v-for="item in templateDetailFields(detailRow)"
          :key="item.label"
          :label="item.label"
        >
          <span :class="{ 'mono-id': item.label === '唯一 ID' }">{{ item.value }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button type="primary" @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="templateDialogVisible"
      :title="editingTemplateId ? '编辑机柜样式模板' : '新建机柜样式模板'"
      width="960px"
      destroy-on-close
    >
      <div class="create-layout">
        <div class="create-form">
          <el-form label-width="90px">
            <el-form-item label="编号" required>
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
            <el-form-item label="视觉样式" required>
              <div class="style-thumbs" role="radiogroup" aria-label="视觉样式">
                <button
                  v-for="item in VISUAL_STYLE_OPTIONS"
                  :key="item.value"
                  type="button"
                  class="style-thumb"
                  :class="{ active: templateForm.visual_style === item.value }"
                  :title="item.hint"
                  :aria-pressed="templateForm.visual_style === item.value"
                  @click="templateForm.visual_style = item.value"
                >
                  <div class="style-thumb-preview">
                    <RackCabinet
                      :code="item.label.slice(0, 2)"
                      :total-u="8"
                      :slots="STYLE_THUMB_SLOTS"
                      :total-power="160"
                      :visual-style="item.value"
                      compact
                    />
                  </div>
                  <span class="style-thumb-label">{{ item.label }}</span>
                </button>
              </div>
              <div class="field-hint">
                {{ VISUAL_STYLE_OPTIONS.find((o) => o.value === templateForm.visual_style)?.hint }}
              </div>
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="templateForm.description" type="textarea" :rows="2" />
            </el-form-item>
          </el-form>
        </div>
        <div class="create-preview">
          <div class="preview-title">样式预览 · {{ visualStyleLabel(templateForm.visual_style) }}</div>
          <RackCabinet
            :code="templatePreviewCode"
            :total-u="templateForm.total_u"
            :slots="templatePreviewSlots"
            :total-power="280"
            :visual-style="templateForm.visual_style"
            compact
          />
        </div>
      </div>
      <template #footer>
        <el-button @click="templateDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTemplate">保存模板</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="applyVisible" title="应用模板到机房" width="720px" destroy-on-close>
      <el-form label-width="110px">
        <el-form-item label="样式模板" required>
          <el-select
            v-model="applyForm.template_id"
            style="width: 100%"
            :disabled="applyLockTemplate"
          >
            <el-option
              v-for="t in templates"
              :key="t.id"
              :label="`${t.name}（${t.total_u}U · ${visualStyleLabel(t.visual_style)}）`"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="视觉样式" required>
          <div class="style-thumbs" role="radiogroup" aria-label="视觉样式">
            <button
              v-for="item in VISUAL_STYLE_OPTIONS"
              :key="item.value"
              type="button"
              class="style-thumb"
              :class="{ active: applyForm.visual_style === item.value }"
              :title="item.hint"
              :aria-pressed="applyForm.visual_style === item.value"
              @click="applyForm.visual_style = item.value"
            >
              <div class="style-thumb-preview">
                <RackCabinet
                  :code="item.label.slice(0, 2)"
                  :total-u="8"
                  :slots="STYLE_THUMB_SLOTS"
                  :total-power="160"
                  :visual-style="item.value"
                  compact
                />
              </div>
              <span class="style-thumb-label">{{ item.label }}</span>
            </button>
          </div>
          <div class="field-hint">
            {{ VISUAL_STYLE_OPTIONS.find((o) => o.value === applyForm.visual_style)?.hint }}
            <template v-if="applyTemplate && normalizeVisualStyle(applyTemplate.visual_style) !== applyForm.visual_style">
              （已覆盖模板默认「{{ visualStyleLabel(applyTemplate.visual_style) }}」）
            </template>
          </div>
        </el-form-item>
        <el-form-item label="目标机房" required>
          <el-select
            v-model="applyForm.room_ids"
            multiple
            collapse-tags
            collapse-tags-tooltip
            filterable
            style="width: 100%"
            placeholder="选择一个或多个机房"
          >
            <el-option v-for="room in rooms" :key="room.id" :label="roomLabel(room)" :value="room.id" />
          </el-select>
          <div v-if="applyForm.room_ids.length" class="field-hint">
            已选 {{ applyForm.room_ids.length }} 个机房
          </div>
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
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hero {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 22px;
  border-radius: 12px;
  border: 1px solid #d7e3ef;
  background:
    radial-gradient(ellipse at 0% 0%, rgba(58, 160, 255, 0.12), transparent 50%),
    linear-gradient(135deg, #f7fbff 0%, #e8f1fa 100%);
}

.hero-copy h2 {
  margin: 0;
  font-size: 22px;
  color: #1f2d3d;
}

.hero-copy p {
  margin: 8px 0 0;
  color: #5f6b7a;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.list-card :deep(.el-card__header) {
  padding: 12px 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.field-hint {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}

.mono-id {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  color: #606266;
}

.muted {
  color: #c0c4cc;
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

@media (max-width: 900px) {
  .create-layout {
    grid-template-columns: 1fr;
  }
}

.style-thumbs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  width: 100%;
}

.style-thumb {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 6px;
  margin: 0;
  padding: 8px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fafbfc;
  cursor: pointer;
  text-align: center;
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
  font: inherit;
  color: inherit;
}

.style-thumb:hover {
  border-color: #c0c4cc;
  background: #fff;
}

.style-thumb.active {
  border-color: var(--el-color-primary);
  background: #fff;
  box-shadow: 0 0 0 1px var(--el-color-primary);
}

.style-thumb-preview {
  height: 128px;
  overflow: hidden;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  pointer-events: none;
  border-radius: 4px;
  background: #f3f4f6;
}

.style-thumb-preview :deep(.cabinet) {
  transform: scale(0.42);
  transform-origin: top center;
  max-width: none !important;
}

.style-thumb-preview :deep(.style-grid) {
  transform: scale(0.5);
}

.style-thumb-label {
  font-size: 12px;
  font-weight: 600;
  color: #303133;
  line-height: 1.2;
}

.style-thumb.active .style-thumb-label {
  color: var(--el-color-primary);
}
</style>
