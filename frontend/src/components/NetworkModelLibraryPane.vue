<script setup lang="ts">
import { computed, nextTick, reactive } from 'vue'
import TopologyDeviceIcon from '@/components/TopologyDeviceIcon.vue'
import type { NetworkDesignModel } from '@/api/networkModelDesign'
import { designModelIconProps } from '@/utils/designModelIcon'
import { setDesignModelDragData } from '@/utils/topologyDnd'

const props = defineProps<{
  rootFolderId: string | null
  models: NetworkDesignModel[]
  selectedModelId: string | null
  disabled?: boolean
  hideTitle?: boolean
  loading?: boolean
}>()

const emit = defineEmits<{
  select: [modelId: string]
  /** 右键批量部署：打开数量对话框 */
  batchDeploy: [modelId: string]
}>()

/** 预计算图标参数，避免列表每次渲染重复推导 */
const modelRows = computed(() =>
  props.models.map((m) => ({
    model: m,
    icon: designModelIconProps(m),
  })),
)

const ctx = reactive({
  visible: false,
  x: 0,
  y: 0,
  modelId: '' as string,
  modelName: '',
})

function onDragStart(event: DragEvent, modelId: string) {
  if (props.disabled || !event.dataTransfer) {
    event.preventDefault()
    return
  }
  setDesignModelDragData(event.dataTransfer, modelId)
  emit('select', modelId)
}

function closeCtx() {
  ctx.visible = false
}

function onContextMenu(event: MouseEvent, model: NetworkDesignModel) {
  if (props.disabled) return
  event.preventDefault()
  event.stopPropagation()
  ctx.modelId = model.id
  ctx.modelName = model.name
  ctx.x = event.clientX
  ctx.y = event.clientY
  ctx.visible = true
  void nextTick(() => {
    const el = document.getElementById('model-lib-ctx-menu')
    if (!el) return
    const rect = el.getBoundingClientRect()
    const maxX = window.innerWidth - rect.width - 8
    const maxY = window.innerHeight - rect.height - 8
    ctx.x = Math.max(8, Math.min(ctx.x, maxX))
    ctx.y = Math.max(8, Math.min(ctx.y, maxY))
  })
}

function ctxSelectPlace() {
  if (!ctx.modelId) return
  emit('select', ctx.modelId)
  closeCtx()
}

function ctxBatchDeploy() {
  if (!ctx.modelId) return
  emit('batchDeploy', ctx.modelId)
  closeCtx()
}

const menuStyle = computed(() => ({
  left: `${ctx.x}px`,
  top: `${ctx.y}px`,
}))
</script>

<template>
  <div class="model-library" v-loading="loading" @click="closeCtx">
    <div v-if="!hideTitle" class="side-title">
      模型库
      <span v-if="rootFolderId" class="count">{{ models.length }}</span>
    </div>
    <div v-else-if="rootFolderId" class="count-row">
      <span class="count">{{ models.length }} 个模型</span>
    </div>
    <template v-if="!rootFolderId">
      <el-empty description="请先选择项目或文件夹" :image-size="56" />
    </template>
    <template v-else-if="!models.length && !loading">
      <div class="empty-hint">该目录下暂无模型</div>
    </template>
    <template v-else>
      <div class="place-hint">
        点击/拖拽到画布放置；右键可指定数量批量部署
      </div>
      <div class="model-list">
        <button
          v-for="row in modelRows"
          :key="row.model.id"
          type="button"
          class="model-card"
          :class="{ active: selectedModelId === row.model.id }"
          :disabled="disabled"
          :draggable="!disabled"
          title="左键选中后点画布 / 拖到画布；右键批量部署"
          @click="emit('select', row.model.id)"
          @dragstart="onDragStart($event, row.model.id)"
          @contextmenu="onContextMenu($event, row.model)"
        >
          <TopologyDeviceIcon v-bind="row.icon" :size="36" />
          <div class="meta">
            <span class="name">
              {{ row.model.name }}
              <span v-if="!row.model.is_published" class="draft">未发布</span>
            </span>
            <span class="sub">
              <template v-if="row.model.code">{{ row.model.code }} · </template>
              {{ row.model.category }}/{{ row.model.subtype }}
            </span>
          </div>
        </button>
      </div>
    </template>

    <Teleport to="body">
      <div
        v-if="ctx.visible"
        class="ctx-backdrop"
        @click="closeCtx"
        @contextmenu.prevent="closeCtx"
      />
      <div
        v-if="ctx.visible"
        id="model-lib-ctx-menu"
        class="ctx-menu"
        :style="menuStyle"
        @click.stop
      >
        <div class="ctx-title">{{ ctx.modelName }}</div>
        <button type="button" class="ctx-item" @click="ctxSelectPlace">
          选中并点击画布放置
        </button>
        <button type="button" class="ctx-item primary" @click="ctxBatchDeploy">
          批量部署…
        </button>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.model-library {
  margin-top: 4px;
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.side-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.count-row {
  margin-bottom: 6px;
}
.count {
  font-size: 11px;
  font-weight: 500;
  color: #909399;
  background: #f0f2f5;
  border-radius: 10px;
  padding: 0 6px;
  line-height: 18px;
}
.place-hint {
  font-size: 11px;
  color: #909399;
  line-height: 1.4;
  margin-bottom: 6px;
}
.empty-hint {
  font-size: 12px;
  color: #909399;
  padding: 8px 0;
}
.model-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  max-height: min(560px, 62vh);
  overflow: auto;
}
.model-card {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 8px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #fff;
  cursor: grab;
  text-align: left;
}
.model-card:active:not(:disabled) {
  cursor: grabbing;
}
.model-card:hover:not(:disabled) {
  border-color: #409eff;
  background: #f5faff;
}
.model-card.active {
  border-color: #409eff;
  background: #ecf5ff;
  box-shadow: inset 0 0 0 1px #409eff;
}
.model-card:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 2px;
}
.name {
  font-size: 12px;
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 4px;
}
.draft {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 500;
  color: #e6a23c;
  background: #fdf6ec;
  border-radius: 2px;
  padding: 0 4px;
  line-height: 16px;
}
.sub {
  font-size: 11px;
  color: #909399;
}
</style>

<style>
.ctx-backdrop {
  position: fixed;
  inset: 0;
  z-index: 4000;
}
.ctx-menu {
  position: fixed;
  z-index: 4001;
  min-width: 180px;
  padding: 6px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
}
.ctx-title {
  font-size: 11px;
  color: #909399;
  padding: 4px 8px 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
}
.ctx-item {
  display: block;
  width: 100%;
  border: none;
  background: transparent;
  text-align: left;
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 13px;
  color: #303133;
  cursor: pointer;
}
.ctx-item:hover {
  background: #f5f7fa;
}
.ctx-item.primary {
  color: #409eff;
  font-weight: 600;
}
.ctx-item.primary:hover {
  background: #ecf5ff;
}
</style>
