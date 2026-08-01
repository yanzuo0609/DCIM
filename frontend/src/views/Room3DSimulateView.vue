<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import RoomWebGLScene from '@/components/RoomWebGLScene.vue'
import { listRooms } from '@/api/room'
import {
  cellKindLabel,
  isPlaceableKind,
  type CellKind,
  type CellProp,
} from '@/utils/roomSceneLayout'
import {
  createCustomSceneModel,
  loadCustomSceneModels,
  removeCustomSceneModel,
  type CustomSceneModel,
} from '@/utils/sceneCustomModels'

const route = useRoute()
const router = useRouter()
const showAllCards = ref(true)
const renderLevel = ref<'1' | '2'>('1')
const selectedRoomId = ref('')
const preferredRoomId = ref<string | null>(null)
const sceneRef = ref<{
  placeLibraryItem: (
    kind: CellKind,
    x: number,
    y: number,
    meta?: CellProp | null,
  ) => boolean
  getHostEl: () => HTMLElement | null
} | null>(null)
const sceneEditing = ref(false)
const selectedLibKey = ref<string | null>(null)
const customModels = ref<CustomSceneModel[]>(loadCustomSceneModels())
const customNameDraft = ref('')
const customColorDraft = ref('#5a7a9a')
const showCustomForm = ref(false)

type LibItem = {
  key: string
  name: string
  kind: CellKind
  placeable: true
  meta?: CellProp
  customId?: string
  color?: string
}

const builtinItems: LibItem[] = [
  { key: 'pillar', name: '方形立柱', kind: 'pillar', placeable: true },
  { key: 'pillar_round', name: '圆形立柱', kind: 'pillar_round', placeable: true },
  { key: 'pdu', name: '列头柜', kind: 'pdu', placeable: true },
  { key: 'rack', name: '标准机柜', kind: 'rack', placeable: true },
  { key: 'power', name: '电柜', kind: 'power', placeable: true },
  { key: 'ac', name: '空调柜', kind: 'ac', placeable: true },
  { key: 'odf', name: 'ODF架', kind: 'odf', placeable: true },
]

const libraryItems = computed<LibItem[]>(() => [
  ...builtinItems,
  ...customModels.value.map((m) => ({
    key: `custom:${m.id}`,
    name: m.name,
    kind: 'custom' as const,
    placeable: true as const,
    customId: m.id,
    color: m.color,
    meta: { label: m.name, color: m.color, customId: m.id },
  })),
])

const selectedLibItem = computed(
  () => libraryItems.value.find((i) => i.key === selectedLibKey.value) || null,
)
const selectedLibKind = computed(() => selectedLibItem.value?.kind || null)
const selectedLibMeta = computed(() => selectedLibItem.value?.meta || null)

function onEditModeChange(editing: boolean) {
  sceneEditing.value = editing
  if (!editing) {
    selectedLibKey.value = null
    showCustomForm.value = false
  }
}

const stats = ref({
  roomTitle: '3D 机房仿真',
  deviceTotal: 0,
  danger: 0,
  fault: 0,
  spaceLabel: '0/0',
})

const DRAG_MIME = 'application/x-dcim-scene-kind'
const DRAG_META_MIME = 'application/x-dcim-scene-meta'

async function resolvePreferredRoom() {
  const roomId = typeof route.query.room_id === 'string' ? route.query.room_id : ''
  if (roomId) {
    preferredRoomId.value = roomId
    return
  }
  const dcId = typeof route.query.datacenter_id === 'string' ? route.query.datacenter_id : ''
  if (!dcId) {
    preferredRoomId.value = null
    return
  }
  try {
    const res = await listRooms({ page: 1, page_size: 200, datacenter_id: dcId || undefined })
    const match = res.items.find((r) => r.datacenter_id === dcId)
    preferredRoomId.value = match?.id || null
  } catch {
    preferredRoomId.value = null
  }
}

function onStats(payload: {
  roomId: string
  roomTitle: string
  deviceTotal: number
  danger: number
  fault: number
  occupied: number
  total: number
}) {
  selectedRoomId.value = payload.roomId
  stats.value = {
    roomTitle: payload.roomTitle,
    deviceTotal: payload.deviceTotal,
    danger: payload.danger,
    fault: payload.fault,
    spaceLabel: `${payload.occupied}/${payload.total}`,
  }
}

function goManageLayout() {
  void router.push({
    name: 'rooms-manage',
    query: selectedRoomId.value ? { open_layout: selectedRoomId.value } : undefined,
  })
}

function goTemplates() {
  void router.push({ name: 'room-rack-templates' })
}

function goDatacenters() {
  void router.push({ name: 'datacenters' })
}

function onLibDragStart(event: DragEvent, item: LibItem) {
  selectedLibKey.value = item.key
  if (!event.dataTransfer) {
    event.preventDefault()
    return
  }
  event.dataTransfer.setData(DRAG_MIME, item.kind)
  event.dataTransfer.setData('text/plain', item.kind)
  if (item.meta) {
    event.dataTransfer.setData(DRAG_META_MIME, JSON.stringify(item.meta))
  }
  event.dataTransfer.effectAllowed = 'copy'
}

function selectLibItem(item: LibItem) {
  if (selectedLibKey.value === item.key) {
    selectedLibKey.value = null
    return
  }
  selectedLibKey.value = item.key
}

function onCanvasDragOver(event: DragEvent) {
  if (
    !event.dataTransfer?.types.includes(DRAG_MIME) &&
    !event.dataTransfer?.types.includes('text/plain')
  ) {
    return
  }
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy'
}

function parseDropMeta(raw: string): CellProp | null {
  if (!raw) return null
  try {
    const obj = JSON.parse(raw) as CellProp
    if (!obj || typeof obj !== 'object') return null
    return {
      label: typeof obj.label === 'string' ? obj.label : undefined,
      color: typeof obj.color === 'string' ? obj.color : undefined,
      customId: typeof obj.customId === 'string' ? obj.customId : undefined,
    }
  } catch {
    return null
  }
}

function onCanvasDrop(event: DragEvent) {
  event.preventDefault()
  const raw =
    event.dataTransfer?.getData(DRAG_MIME) || event.dataTransfer?.getData('text/plain') || ''
  if (!isPlaceableKind(raw)) return
  const meta = parseDropMeta(event.dataTransfer?.getData(DRAG_META_MIME) || '')
  const ok = sceneRef.value?.placeLibraryItem(raw, event.clientX, event.clientY, meta)
  if (ok) {
    ElMessage.success(`已放置${meta?.label || cellKindLabel(raw)}`)
  } else {
    ElMessage.warning('请先开启「编辑场景」，并将模型拖到机房地板上')
  }
}

function addCustomModel() {
  const name = customNameDraft.value.trim()
  if (!name) {
    ElMessage.warning('请输入自定义模型名称')
    return
  }
  if (customModels.value.some((m) => m.name === name)) {
    ElMessage.warning('已存在同名自定义模型')
    return
  }
  const model = createCustomSceneModel(name, customColorDraft.value)
  customModels.value = loadCustomSceneModels()
  selectedLibKey.value = `custom:${model.id}`
  customNameDraft.value = ''
  showCustomForm.value = false
  ElMessage.success(`已添加自定义模型「${model.name}」`)
}

async function deleteCustomModel(item: LibItem, event: Event) {
  event.stopPropagation()
  if (!item.customId) return
  try {
    await ElMessageBox.confirm(
      `删除自定义模型「${item.name}」？不影响已放置到场景中的实例。`,
      '删除确认',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      },
    )
  } catch {
    return
  }
  customModels.value = removeCustomSceneModel(item.customId)
  if (selectedLibKey.value === item.key) selectedLibKey.value = null
  ElMessage.success('已删除自定义模型')
}

watch(
  () => [route.query.room_id, route.query.datacenter_id],
  () => {
    void resolvePreferredRoom()
  },
)

onMounted(() => {
  void resolvePreferredRoom()
})
</script>

<template>
  <div class="simulate-page">
    <header class="sim-top">
      <div class="sim-brand">
        <strong>3D 机房</strong>
        <span class="sim-crumb">{{ stats.roomTitle }}</span>
      </div>
      <div class="sim-actions">
        <el-select v-model="renderLevel" size="small" style="width: 148px">
          <el-option label="渲染质量 · 级别一" value="1" />
          <el-option label="渲染质量 · 级别二" value="2" />
        </el-select>
        <el-checkbox v-model="showAllCards" size="small">显示全部卡片</el-checkbox>
        <el-button size="small" @click="goDatacenters">数据中心</el-button>
        <el-button type="primary" size="small" @click="goManageLayout">配置所在机房</el-button>
        <el-button size="small" @click="goTemplates">机柜模板</el-button>
      </div>
    </header>

    <div class="sim-stage" :class="{ editing: sceneEditing }">
      <div class="sim-canvas" @dragover="onCanvasDragOver" @drop="onCanvasDrop">
        <RoomWebGLScene
          ref="sceneRef"
          :preferred-room-id="preferredRoomId"
          :quality="renderLevel"
          :brush-kind="selectedLibKind"
          :brush-meta="selectedLibMeta"
          @stats="onStats"
          @edit-mode-change="onEditModeChange"
        />
      </div>

      <aside v-if="sceneEditing" class="sim-library" aria-label="内置常用模型">
        <h4>内置常用模型</h4>
        <div class="lib-grid">
          <div
            v-for="item in libraryItems"
            :key="item.key"
            class="lib-item placeable"
            :class="{ selected: selectedLibKey === item.key, custom: !!item.customId }"
            draggable="true"
            @click="selectLibItem(item)"
            @dragstart="onLibDragStart($event, item)"
          >
            <span class="lib-ring" aria-hidden="true" />
            <span
              class="lib-icon"
              :data-kind="item.kind === 'custom' ? '自定义' : item.name"
              :style="item.color ? { '--custom-color': item.color } : undefined"
            />
            <span class="lib-name">{{ item.name }}</span>
            <em class="lib-drag-tip">可拖放</em>
            <button
              v-if="item.customId"
              type="button"
              class="lib-del"
              title="删除自定义模型"
              @click="deleteCustomModel(item, $event)"
            >
              ×
            </button>
          </div>
        </div>

        <div class="lib-custom">
          <button
            type="button"
            class="lib-custom-toggle"
            @click="showCustomForm = !showCustomForm"
          >
            {{ showCustomForm ? '收起' : '+ 自定义模型' }}
          </button>
          <div v-if="showCustomForm" class="lib-custom-form">
            <input
              v-model="customNameDraft"
              class="lib-custom-input"
              maxlength="20"
              placeholder="名称，如消防柜"
              @keydown.enter.prevent="addCustomModel"
            />
            <label class="lib-color">
              <span>颜色</span>
              <input v-model="customColorDraft" type="color" />
            </label>
            <button type="button" class="lib-custom-add" @click="addCustomModel">添加</button>
          </div>
        </div>

        <p class="lib-hint">
          选中模型后点「替换」，或直接拖到地板。支持立柱、ODF架、电柜、空调柜与自定义。改完请保存布局。
        </p>
      </aside>

      <div v-if="showAllCards" class="sim-cards">
        <article class="stat-card">
          <i class="dot blue" />
          <div>
            <span>设备总数</span>
            <strong>{{ stats.deviceTotal }}</strong>
          </div>
        </article>
        <article class="stat-card">
          <i class="dot yellow" />
          <div>
            <span>危险</span>
            <strong>{{ stats.danger }}</strong>
          </div>
        </article>
        <article class="stat-card">
          <i class="dot red" />
          <div>
            <span>故障</span>
            <strong>{{ stats.fault }}</strong>
          </div>
        </article>
        <article class="stat-card">
          <i class="dot cyan" />
          <div>
            <span>机柜空间</span>
            <strong>{{ stats.spaceLabel }}</strong>
          </div>
        </article>
      </div>
    </div>
  </div>
</template>

<style scoped>
.simulate-page {
  --sim-bg: #e8f0f8;
  --sim-panel: rgba(255, 255, 255, 0.92);
  --sim-line: #d7e3ef;
  --sim-text: #1f2d3d;
  --sim-muted: #6b7c8f;
  min-height: calc(100vh - 140px);
  display: flex;
  flex-direction: column;
  gap: 12px;
  color: var(--sim-text);
}

.sim-top {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  background: var(--sim-panel);
  border: 1px solid var(--sim-line);
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(31, 45, 61, 0.04);
}

.sim-brand {
  display: flex;
  align-items: baseline;
  gap: 12px;
  min-width: 0;
}

.sim-brand strong {
  font-size: 18px;
  letter-spacing: 0.04em;
}

.sim-crumb {
  color: var(--sim-muted);
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sim-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.sim-stage {
  position: relative;
  flex: 1;
  min-height: 560px;
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.sim-stage.editing {
  grid-template-columns: 1fr 220px;
}

.sim-canvas {
  position: relative;
  min-width: 0;
  min-height: 560px;
  border-radius: 12px;
  border: 1px solid var(--sim-line);
  background: radial-gradient(ellipse at 50% 0%, #f4f9ff 0%, #d9e8f6 55%, #c8daf0 100%);
  overflow: hidden;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.5);
}

.sim-canvas :deep(.webgl-room) {
  height: 100%;
}

.sim-library {
  background: var(--sim-panel);
  border: 1px solid var(--sim-line);
  border-radius: 10px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: calc(100vh - 220px);
  overflow: auto;
}

.sim-library h4 {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
}

.lib-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.lib-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 6px;
  border: 1px solid #8eb6de;
  border-radius: 8px;
  background: #eef6ff;
  font-size: 11px;
  color: #2a4a6a;
  text-align: center;
  user-select: none;
  cursor: grab;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    background 0.15s ease,
    transform 0.15s ease;
}

.lib-item:active {
  cursor: grabbing;
}

.lib-name {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lib-ring {
  position: absolute;
  inset: 4px;
  border-radius: 10px;
  border: 2px solid transparent;
  pointer-events: none;
  opacity: 0;
}

.lib-item.selected {
  border-color: #2f6fed;
  background: #e8f1ff;
  color: #1a4a8a;
  box-shadow: 0 0 0 3px rgba(47, 111, 237, 0.18);
  transform: translateY(-1px);
}

.lib-item.selected .lib-ring {
  opacity: 1;
  border-color: #3aa0ff;
  box-shadow:
    0 0 0 2px rgba(58, 160, 255, 0.35),
    inset 0 0 0 1px rgba(255, 255, 255, 0.6);
}

.lib-del {
  position: absolute;
  top: 2px;
  right: 4px;
  width: 18px;
  height: 18px;
  border: none;
  border-radius: 50%;
  background: rgba(227, 93, 91, 0.12);
  color: #c0392b;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  padding: 0;
}

.lib-del:hover {
  background: #e35d5b;
  color: #fff;
}

.lib-drag-tip {
  font-style: normal;
  font-size: 10px;
  color: #3aa0ff;
}

.lib-icon {
  width: 26px;
  height: 40px;
  border-radius: 2px;
  background: linear-gradient(180deg, #32353a 0%, #2b2d31 45%, #1a1c20 100%);
  border: 1px solid #0c0d0f;
  box-shadow: 0 2px 6px rgba(20, 40, 70, 0.18);
  position: relative;
  overflow: hidden;
}

.lib-icon::before {
  content: '';
  position: absolute;
  left: 3px;
  right: 3px;
  top: 3px;
  bottom: 4px;
  border-radius: 1px;
  background: linear-gradient(180deg, #5ab0ff 0%, #3aa0ff 55%, #2f8ae0 100%);
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.18),
    inset 0 -2px 4px rgba(0, 0, 0, 0.25);
}

.lib-icon::after {
  content: '';
  position: absolute;
  left: 5px;
  right: 5px;
  top: 8px;
  bottom: 8px;
  background: repeating-linear-gradient(
    to bottom,
    transparent 0 5px,
    rgba(26, 28, 32, 0.55) 5px 7px
  );
}

.lib-icon[data-kind='方形立柱'] {
  width: 22px;
  height: 40px;
  background: linear-gradient(180deg, #9aa8b8, #7a8b9c 40%, #6a7c90);
  border-radius: 2px;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.2);
}

.lib-icon[data-kind='方形立柱']::before,
.lib-icon[data-kind='方形立柱']::after {
  display: none;
}

.lib-icon[data-kind='圆形立柱'] {
  width: 22px;
  height: 40px;
  background: linear-gradient(180deg, #9aa8b8, #7a8b9c 40%, #6a7c90);
  border-radius: 11px;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.2);
}

.lib-icon[data-kind='圆形立柱']::before,
.lib-icon[data-kind='圆形立柱']::after {
  display: none;
}

.lib-icon[data-kind='立柱'] {
  width: 22px;
  height: 40px;
  background: linear-gradient(180deg, #9aa8b8, #7a8b9c 40%, #6a7c90);
  border-radius: 2px;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.2);
}

.lib-icon[data-kind='立柱']::before,
.lib-icon[data-kind='立柱']::after {
  display: none;
}

.lib-icon[data-kind='列头柜'] {
  height: 30px;
  background: linear-gradient(180deg, #3d4555, #2a303c);
  box-shadow: inset 3px 0 0 #f0a020;
}

.lib-icon[data-kind='列头柜']::before {
  left: 6px;
  background: linear-gradient(180deg, #4a5568, #2a303c);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
}

.lib-icon[data-kind='列头柜']::after {
  left: 8px;
  right: 4px;
  background: repeating-linear-gradient(
    to bottom,
    transparent 0 3px,
    rgba(240, 160, 32, 0.35) 3px 4px
  );
}

.lib-icon[data-kind='电柜'] {
  height: 36px;
  background: linear-gradient(180deg, #4a5058, #2f343c);
  box-shadow: inset 3px 0 0 #f5c542;
}

.lib-icon[data-kind='电柜']::before {
  background: linear-gradient(180deg, #5a616a, #3a4048);
  box-shadow: inset 0 0 0 1px rgba(245, 197, 66, 0.35);
}

.lib-icon[data-kind='电柜']::after {
  background: repeating-linear-gradient(
    to bottom,
    transparent 0 3px,
    rgba(245, 197, 66, 0.4) 3px 4px
  );
}

.lib-icon[data-kind='空调柜'] {
  height: 38px;
  background: linear-gradient(180deg, #4a6a80, #2f4558);
  box-shadow: inset 3px 0 0 #3aa0ff;
}

.lib-icon[data-kind='空调柜']::before {
  background: linear-gradient(180deg, #6a98b0, #3a5568);
}

.lib-icon[data-kind='空调柜']::after {
  background: repeating-linear-gradient(
    to bottom,
    transparent 0 3px,
    rgba(142, 182, 208, 0.55) 3px 4px
  );
}

.lib-icon[data-kind='ODF架'] {
  width: 26px;
  height: 40px;
  background: linear-gradient(180deg, #3a4250, #232833);
  box-shadow: inset 3px 0 0 #f0b429;
}

.lib-icon[data-kind='ODF架']::before {
  background: linear-gradient(180deg, #2a3140, #1a1f28);
}

.lib-icon[data-kind='ODF架']::after {
  left: 6px;
  right: 5px;
  top: 7px;
  bottom: 7px;
  background: repeating-linear-gradient(
    to bottom,
    transparent 0 2px,
    rgba(240, 180, 41, 0.55) 2px 3px
  );
}

.lib-icon[data-kind='自定义'] {
  width: 26px;
  height: 40px;
  background: linear-gradient(180deg, #4a5568, #2d3644);
  box-shadow: inset 3px 0 0 var(--custom-color, #5a7a9a);
}

.lib-icon[data-kind='自定义']::before {
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--custom-color, #5a7a9a) 70%, #fff),
    var(--custom-color, #5a7a9a)
  );
}

.lib-icon[data-kind='自定义']::after {
  display: none;
}

.lib-custom {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 4px;
  border-top: 1px dashed var(--sim-line);
}

.lib-custom-toggle {
  height: 30px;
  border-radius: 6px;
  border: 1px dashed #8eb6de;
  background: #f5f9fd;
  color: #1a6fd0;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.lib-custom-toggle:hover {
  border-style: solid;
  background: #e8f3ff;
}

.lib-custom-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.lib-custom-input {
  height: 30px;
  border-radius: 6px;
  border: 1px solid #b8cce0;
  padding: 0 8px;
  font-size: 12px;
}

.lib-color {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  color: var(--sim-muted);
}

.lib-color input[type='color'] {
  width: 42px;
  height: 28px;
  border: 1px solid #b8cce0;
  border-radius: 4px;
  padding: 0;
  background: #fff;
  cursor: pointer;
}

.lib-custom-add {
  height: 30px;
  border-radius: 6px;
  border: none;
  background: #3aa0ff;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.lib-hint {
  margin: auto 0 0;
  font-size: 11px;
  color: var(--sim-muted);
  line-height: 1.45;
}

.sim-cards {
  position: absolute;
  left: 16px;
  right: 240px;
  bottom: 16px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  pointer-events: none;
  z-index: 5;
}

.stat-card {
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid var(--sim-line);
  box-shadow: 0 6px 18px rgba(40, 70, 110, 0.1);
}

.stat-card span {
  display: block;
  font-size: 11px;
  color: var(--sim-muted);
}

.stat-card strong {
  font-size: 20px;
  font-weight: 700;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot.blue {
  background: #3aa0ff;
}
.dot.yellow {
  background: #f0b429;
}
.dot.red {
  background: #e35d5b;
}
.dot.cyan {
  background: #2dd4bf;
}

@media (max-width: 960px) {
  .sim-stage {
    grid-template-columns: 1fr;
  }

  .sim-library {
    order: 2;
    max-height: none;
  }

  .sim-cards {
    right: 16px;
  }
}
</style>
