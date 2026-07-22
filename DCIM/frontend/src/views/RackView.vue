<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  applyTemplateToRoom,
  createRackTemplate,
  deleteRackTemplate,
  listRackTemplates,
  updateRackTemplate,
  type RackTemplate,
} from '@/api/rack'
import { listRooms, type Room } from '@/api/room'
import { useAuthStore } from '@/stores/auth'
import RackCabinet from '@/components/RackCabinet.vue'

const auth = useAuthStore()
const templates = ref<RackTemplate[]>([])
const rooms = ref<Room[]>([])

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
})

const applyTemplate = computed(
  () => templates.value.find((t) => t.id === applyForm.template_id) || null,
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
  description: '',
})

const templatePreviewCode = computed(() => templateForm.code || templateForm.name || '模板预览')

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
    `将模板「${tpl?.name}」应用到 ${applyForm.room_ids.length} 个机房？\n${roomLabels}\n` +
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

onMounted(() => {
  void Promise.all([refreshTemplates(), loadRooms()])
})
</script>

<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <div>
            <span>机柜样式模板</span>
            <p class="header-hint">维护机柜外观与 U 位规格，可批量应用到单个或多个机房</p>
          </div>
          <div class="header-actions">
            <el-button v-if="canUpdate" @click="openApply()">应用到机房</el-button>
            <el-button v-if="canCreate" type="primary" @click="openCreateTemplate">新建模板</el-button>
          </div>
        </div>
      </template>

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
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canUpdate" type="primary" link @click="openApply(row.id)">应用到机房</el-button>
            <el-button v-if="canUpdate" type="primary" link @click="openEditTemplate(row)">编辑</el-button>
            <el-button v-if="canDelete" type="danger" link @click="handleDeleteTemplate(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

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

    <el-dialog v-model="applyVisible" title="应用模板到机房" width="560px" destroy-on-close>
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
              :label="`${t.name}（${t.total_u}U）`"
              :value="t.id"
            />
          </el-select>
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

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.field-hint {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}

.header-hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: #909399;
  font-weight: normal;
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
</style>
