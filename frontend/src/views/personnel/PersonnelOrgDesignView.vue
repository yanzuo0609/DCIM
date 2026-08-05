<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createOrgChart,
  deleteOrgChart,
  getOrgChart,
  listOrgCharts,
  updateOrgChart,
  type OrgChart,
  type OrgChartBrief,
  type OrgLink,
  type OrgNode,
} from '@/api/personnel'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const canEdit = computed(
  () => auth.hasPermission('device:create') || auth.hasPermission('device:update'),
)
const canDelete = auth.hasPermission('device:delete')

const charts = ref<OrgChartBrief[]>([])
const currentId = ref<string | null>(null)
const loading = ref(false)
const saving = ref(false)
const nodes = ref<OrgNode[]>([])
const links = ref<OrgLink[]>([])
const selectedId = ref<string | null>(null)
const linkMode = ref(false)
const linkSourceId = ref<string | null>(null)

const createDialog = ref(false)
const createForm = reactive({ project_no: '', name: '' })

const selected = computed(() => nodes.value.find((n) => n.id === selectedId.value) || null)

const NODE_W = 160
const NODE_H = 72

async function loadCharts() {
  charts.value = await listOrgCharts()
}

async function selectChart(id: string) {
  loading.value = true
  try {
    const chart = await getOrgChart(id)
    currentId.value = chart.id
    nodes.value = chart.nodes.map((n) => ({ ...n }))
    links.value = chart.links.map((l) => ({ ...l }))
    selectedId.value = null
    linkMode.value = false
    linkSourceId.value = null
  } finally {
    loading.value = false
  }
}

async function openCreate() {
  createForm.project_no = ''
  createForm.name = ''
  createDialog.value = true
}

async function submitCreate() {
  if (!createForm.project_no.trim() || !createForm.name.trim()) {
    ElMessage.warning('请填写项目编号与名称')
    return
  }
  const created = await createOrgChart({
    project_no: createForm.project_no.trim(),
    name: createForm.name.trim(),
  })
  createDialog.value = false
  await loadCharts()
  await selectChart(created.id)
  ElMessage.success('已创建组织架构图')
}

async function removeChart() {
  if (!currentId.value) return
  const hit = charts.value.find((c) => c.id === currentId.value)
  await ElMessageBox.confirm(`确定删除「${hit?.name || '组织图'}」吗？`, '确认删除', {
    type: 'warning',
  })
  await deleteOrgChart(currentId.value)
  currentId.value = null
  nodes.value = []
  links.value = []
  await loadCharts()
  ElMessage.success('已删除')
}

function newLocalId() {
  return `tmp-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

function addNode(x = 80, y = 80) {
  if (!canEdit.value || !currentId.value) return
  const id = newLocalId()
  nodes.value.push({
    id,
    chart_id: currentId.value,
    parent_id: null,
    title: '新节点',
    role_title: '',
    person_name: '',
    phone: '',
    email: '',
    pos_x: x,
    pos_y: y,
    sort_order: nodes.value.length,
  })
  selectedId.value = id
}

function removeSelected() {
  if (!selectedId.value) return
  const id = selectedId.value
  nodes.value = nodes.value.filter((n) => n.id !== id)
  links.value = links.value.filter((l) => l.source_node_id !== id && l.target_node_id !== id)
  selectedId.value = null
}

function onNodeClick(id: string) {
  if (linkMode.value) {
    if (!linkSourceId.value) {
      linkSourceId.value = id
      ElMessage.info('请点击下级节点完成连线')
      return
    }
    if (linkSourceId.value === id) {
      linkSourceId.value = null
      return
    }
    const exists = links.value.some(
      (l) => l.source_node_id === linkSourceId.value && l.target_node_id === id,
    )
    if (!exists && currentId.value) {
      links.value.push({
        id: newLocalId(),
        chart_id: currentId.value,
        source_node_id: linkSourceId.value,
        target_node_id: id,
      })
      const child = nodes.value.find((n) => n.id === id)
      if (child) child.parent_id = linkSourceId.value
    }
    linkSourceId.value = null
    return
  }
  selectedId.value = id
}

let dragId: string | null = null
let dragOffsetX = 0
let dragOffsetY = 0

function onNodePointerDown(e: PointerEvent, id: string) {
  if (!canEdit.value || linkMode.value) return
  const node = nodes.value.find((n) => n.id === id)
  if (!node) return
  dragId = id
  selectedId.value = id
  const target = e.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  dragOffsetX = e.clientX - rect.left
  dragOffsetY = e.clientY - rect.top
  target.setPointerCapture(e.pointerId)
}

function onNodePointerMove(e: PointerEvent) {
  if (!dragId || !canEdit.value) return
  const canvas = (e.currentTarget as HTMLElement).closest('.org-canvas') as HTMLElement | null
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const node = nodes.value.find((n) => n.id === dragId)
  if (!node) return
  node.pos_x = Math.max(0, e.clientX - rect.left - dragOffsetX)
  node.pos_y = Math.max(0, e.clientY - rect.top - dragOffsetY)
}

function onNodePointerUp() {
  dragId = null
}

function onCanvasDblClick(e: MouseEvent) {
  if (!canEdit.value || !currentId.value) return
  const canvas = e.currentTarget as HTMLElement
  const rect = canvas.getBoundingClientRect()
  addNode(e.clientX - rect.left - NODE_W / 2, e.clientY - rect.top - NODE_H / 2)
}

function linkPath(link: OrgLink) {
  const s = nodes.value.find((n) => n.id === link.source_node_id)
  const t = nodes.value.find((n) => n.id === link.target_node_id)
  if (!s || !t) return ''
  const x1 = s.pos_x + NODE_W / 2
  const y1 = s.pos_y + NODE_H
  const x2 = t.pos_x + NODE_W / 2
  const y2 = t.pos_y
  const mid = (y1 + y2) / 2
  return `M ${x1} ${y1} C ${x1} ${mid}, ${x2} ${mid}, ${x2} ${y2}`
}

async function saveCanvas() {
  if (!currentId.value) return
  saving.value = true
  try {
    const chart: OrgChart = await updateOrgChart(currentId.value, {
      nodes: nodes.value.map((n, idx) => ({
        id: n.id,
        parent_id: n.parent_id,
        title: n.title || '未命名',
        role_title: n.role_title || null,
        person_name: n.person_name || null,
        phone: n.phone || null,
        email: n.email || null,
        pos_x: n.pos_x,
        pos_y: n.pos_y,
        sort_order: idx,
      })),
      links: links.value.map((l) => ({
        source_node_id: l.source_node_id,
        target_node_id: l.target_node_id,
      })),
    })
    // After save backend regenerates UUIDs for tmp ids — reload
    await selectChart(chart.id)
    await loadCharts()
    ElMessage.success('已保存')
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '保存失败')
  } finally {
    saving.value = false
  }
}

function toggleLinkMode() {
  linkMode.value = !linkMode.value
  linkSourceId.value = null
}

watch(currentId, async (id) => {
  if (id) await selectChart(id)
})

onMounted(async () => {
  await loadCharts()
  if (charts.value.length) {
    currentId.value = charts.value[0].id
  }
})
</script>

<template>
  <div class="org-page" v-loading="loading">
    <div class="toolbar">
      <el-select
        v-model="currentId"
        placeholder="选择组织架构图"
        filterable
        style="width: 280px"
        clearable
      >
        <el-option
          v-for="c in charts"
          :key="c.id"
          :label="`${c.project_no} · ${c.name}`"
          :value="c.id"
        />
      </el-select>
      <el-button v-if="canEdit" type="primary" @click="openCreate">新建组织图</el-button>
      <el-button v-if="canEdit && currentId" @click="addNode()">添加节点</el-button>
      <el-button v-if="canEdit && currentId" :type="linkMode ? 'warning' : 'default'" @click="toggleLinkMode">
        {{ linkMode ? '连线中…' : '连线模式' }}
      </el-button>
      <el-button v-if="canEdit && currentId" type="success" :loading="saving" @click="saveCanvas">
        保存
      </el-button>
      <el-button v-if="canDelete && currentId" type="danger" plain @click="removeChart">删除组织图</el-button>
      <span class="hint">双击画布可添加节点；连线模式：先点上级再点下级</span>
    </div>

    <div class="workspace">
      <div
        class="org-canvas"
        @dblclick="onCanvasDblClick"
        @pointermove="onNodePointerMove"
        @pointerup="onNodePointerUp"
      >
        <svg class="links-layer" xmlns="http://www.w3.org/2000/svg">
          <path
            v-for="link in links"
            :key="link.id"
            :d="linkPath(link)"
            class="org-link"
          />
        </svg>
        <div
          v-for="node in nodes"
          :key="node.id"
          class="org-node"
          :class="{
            selected: selectedId === node.id,
            linkSource: linkSourceId === node.id,
          }"
          :style="{ transform: `translate(${node.pos_x}px, ${node.pos_y}px)` }"
          @click.stop="onNodeClick(node.id)"
          @pointerdown="(e) => onNodePointerDown(e, node.id)"
        >
          <div class="node-title">{{ node.title || '未命名' }}</div>
          <div class="node-meta">{{ node.person_name || node.role_title || '—' }}</div>
        </div>
        <div v-if="!currentId" class="empty">请选择或新建组织架构图</div>
        <div v-else-if="!nodes.length" class="empty">双击画布或点击「添加节点」开始设计</div>
      </div>

      <aside v-if="selected" class="inspector">
        <h4>节点属性</h4>
        <el-form label-width="72px" size="small" :disabled="!canEdit">
          <el-form-item label="标题">
            <el-input v-model="selected.title" />
          </el-form-item>
          <el-form-item label="角色">
            <el-input v-model="selected.role_title" />
          </el-form-item>
          <el-form-item label="姓名">
            <el-input v-model="selected.person_name" />
          </el-form-item>
          <el-form-item label="电话">
            <el-input v-model="selected.phone" />
          </el-form-item>
          <el-form-item label="邮箱">
            <el-input v-model="selected.email" />
          </el-form-item>
        </el-form>
        <el-button v-if="canEdit" type="danger" plain size="small" @click="removeSelected">
          删除节点
        </el-button>
      </aside>
    </div>

    <el-dialog v-model="createDialog" title="新建组织架构图" width="480px">
      <el-form label-width="90px">
        <el-form-item label="项目编号" required>
          <el-input v-model="createForm.project_no" placeholder="与合同项目编号对应" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="createForm.name" placeholder="如：XX项目组织架构" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.org-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: calc(100vh - 180px);
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.hint {
  color: #909399;
  font-size: 12px;
}
.workspace {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 12px;
  flex: 1;
  min-height: 520px;
}
.org-canvas {
  position: relative;
  background:
    linear-gradient(#eef1f6 1px, transparent 1px) 0 0 / 24px 24px,
    linear-gradient(90deg, #eef1f6 1px, transparent 1px) 0 0 / 24px 24px,
    #fafbfc;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  min-height: 520px;
}
.links-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.org-link {
  fill: none;
  stroke: #909399;
  stroke-width: 2;
}
.org-node {
  position: absolute;
  left: 0;
  top: 0;
  width: 160px;
  min-height: 72px;
  padding: 10px 12px;
  background: #fff;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  cursor: grab;
  user-select: none;
  z-index: 1;
}
.org-node.selected {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}
.org-node.linkSource {
  border-color: #e6a23c;
}
.node-title {
  font-weight: 600;
  font-size: 13px;
  color: #303133;
}
.node-meta {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}
.inspector {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 14px;
}
.inspector h4 {
  margin: 0 0 12px;
  font-size: 14px;
}
.empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #909399;
  pointer-events: none;
}
@media (max-width: 960px) {
  .workspace {
    grid-template-columns: 1fr;
  }
}
</style>
