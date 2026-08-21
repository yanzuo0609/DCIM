<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  KPI_OPTIONS,
  SCREEN_MODULE_DEFS,
  SCREEN_THEMES,
  type KpiKey,
  type ScreenLayoutConfig,
  type ScreenSpan,
  type ScreenThemeId,
  moduleDef,
} from '@/utils/screenLayout'
import { useAuthStore } from '@/stores/auth'
import { useScreenStore } from '@/stores/screen'

const router = useRouter()
const auth = useAuthStore()
const screen = useScreenStore()

const saving = ref(false)
const draft = reactive<ScreenLayoutConfig>({
  version: 1,
  title: '',
  theme: 'teal',
  refreshSec: 30,
  kpiKeys: [],
  modules: [],
})

const canManage = computed(
  () =>
    auth.hasPermission('user:view') ||
    auth.hasPermission('role:view') ||
    auth.hasPermission('audit:view') ||
    auth.hasPermission('dashboard:view'),
)

const enabledModuleCount = computed(() => draft.modules.filter((m) => m.enabled).length)
const kpiCount = computed(() => draft.kpiKeys.length)
const sortedModules = computed(() => [...draft.modules].sort((a, b) => a.order - b.order))

const draggingModId = ref<string | null>(null)
const dragOverModId = ref<string | null>(null)

function estimateModColumns() {
  if (typeof window === 'undefined') return 2
  const w = window.innerWidth
  if (w >= 1600) return 4
  if (w >= 1200) return 3
  if (w >= 900) return 2
  return 1
}

function renumberModules(list: typeof draft.modules) {
  draft.modules = list.map((m, i) => ({ ...m, order: i }))
}

function moveModuleBy(id: string, step: number) {
  if (!step) return
  const list = [...draft.modules].sort((a, b) => a.order - b.order)
  const idx = list.findIndex((m) => m.id === id)
  if (idx < 0) return
  const target = Math.min(list.length - 1, Math.max(0, idx + step))
  if (target === idx) return
  const [item] = list.splice(idx, 1)
  list.splice(target, 0, item)
  renumberModules(list)
}

/** 左右：相邻互换；上下：按当前列数跳行 */
function moveModule(id: string, dir: 'left' | 'right' | 'up' | 'down') {
  const cols = estimateModColumns()
  if (dir === 'left') moveModuleBy(id, -1)
  else if (dir === 'right') moveModuleBy(id, 1)
  else if (dir === 'up') moveModuleBy(id, -cols)
  else moveModuleBy(id, cols)
}

function onModDragStart(id: string, event: DragEvent) {
  draggingModId.value = id
  dragOverModId.value = null
  event.dataTransfer?.setData('text/plain', id)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}

function onModDragOver(id: string, event: DragEvent) {
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  if (draggingModId.value && draggingModId.value !== id) dragOverModId.value = id
}

function onModDrop(targetId: string, event: DragEvent) {
  event.preventDefault()
  const sourceId = draggingModId.value || event.dataTransfer?.getData('text/plain') || ''
  dragOverModId.value = null
  draggingModId.value = null
  if (!sourceId || sourceId === targetId) return
  const list = [...draft.modules].sort((a, b) => a.order - b.order)
  const from = list.findIndex((m) => m.id === sourceId)
  const to = list.findIndex((m) => m.id === targetId)
  if (from < 0 || to < 0) return
  const [item] = list.splice(from, 1)
  list.splice(to, 0, item)
  renumberModules(list)
}

function onModDragEnd() {
  draggingModId.value = null
  dragOverModId.value = null
}

const layoutPresets = [
  {
    id: 'balanced',
    label: '均衡布局',
    description: 'KPI + 利用率 + 设备/功耗/网络全开',
    apply: () => {
      draft.modules = SCREEN_MODULE_DEFS.map((def, index) => ({
        id: def.id,
        enabled: true,
        span: def.defaultSpan,
        order: index,
      }))
      draft.kpiKeys = [
        'datacenter_count',
        'room_count',
        'rack_count',
        'device_count',
        'mounted_device_count',
        'total_u',
        'free_u',
        'total_power',
      ]
    },
  },
  {
    id: 'kpi-focus',
    label: '指标聚焦',
    description: '突出 KPI 与利用率，弱化次要图表',
    apply: () => {
      const keep = new Set(['kpi', 'util-gauge', 'u-pie', 'rack-top', 'alert-racks', 'power-room'])
      draft.modules = SCREEN_MODULE_DEFS.map((def, index) => ({
        id: def.id,
        enabled: keep.has(def.id),
        span: def.id === 'kpi' ? 3 : def.id === 'util-gauge' || def.id === 'u-pie' ? 1 : 1,
        order: index,
      }))
      draft.kpiKeys = [
        'device_count',
        'mounted_device_count',
        'utilization',
        'free_u',
        'occupied_u',
        'total_power',
        'mount_ratio',
        'rack_count',
      ]
    },
  },
  {
    id: 'ops',
    label: '值班运维',
    description: '告警、功耗、状态与网络为主',
    apply: () => {
      const keep = new Set([
        'kpi',
        'alert-racks',
        'power-room',
        'device-status',
        'util-buckets',
        'network',
        'contract',
      ])
      draft.modules = SCREEN_MODULE_DEFS.map((def, index) => ({
        id: def.id,
        enabled: keep.has(def.id),
        span: def.id === 'kpi' ? 3 : def.id === 'alert-racks' || def.id === 'power-room' ? 2 : 1,
        order: index,
      }))
      draft.kpiKeys = [
        'rack_count',
        'device_count',
        'utilization',
        'total_power',
        'free_u',
        'mounted_device_count',
      ]
    },
  },
]

function syncDraftFromStore() {
  const cfg = screen.layout
  draft.title = cfg.title
  draft.theme = cfg.theme || 'teal'
  draft.refreshSec = cfg.refreshSec
  draft.kpiKeys = [...cfg.kpiKeys]
  draft.modules = cfg.modules.map((m) => ({ ...m }))
}

function toggleKpi(key: KpiKey, checked: boolean) {
  if (checked) {
    if (!draft.kpiKeys.includes(key)) draft.kpiKeys.push(key)
  } else {
    draft.kpiKeys = draft.kpiKeys.filter((k) => k !== key)
  }
}

function setSpan(id: string, span: ScreenSpan) {
  const row = draft.modules.find((m) => m.id === id)
  if (row) row.span = span
}

function setTheme(id: ScreenThemeId) {
  draft.theme = id
}

function applyPreset(id: string) {
  const preset = layoutPresets.find((p) => p.id === id)
  if (!preset) return
  preset.apply()
  ElMessage.success(`已应用「${preset.label}」预设，请保存生效`)
}

function onMenuEnabledChange(value: boolean | string | number) {
  const enabled = !!value
  screen.setMenuEnabled(enabled)
  ElMessage.success(enabled ? '已开启运营大屏，侧栏将显示入口' : '已关闭运营大屏，侧栏入口已隐藏')
}

function handleSave() {
  saving.value = true
  try {
    const modules = [...draft.modules]
      .sort((a, b) => a.order - b.order)
      .map((m, i) => ({ ...m, order: i }))
    screen.applyLayout({
      version: 1,
      title: draft.title.trim() || '智慧机房管理驾驶舱',
      theme: draft.theme || 'teal',
      refreshSec: draft.refreshSec,
      kpiKeys: draft.kpiKeys.length
        ? draft.kpiKeys
        : (['device_count', 'utilization'] as KpiKey[]),
      modules,
    })
    ElMessage.success('大屏配置已保存')
  } finally {
    saving.value = false
  }
}

function handleReset() {
  const next = screen.restoreDefaultLayout()
  draft.title = next.title
  draft.theme = next.theme
  draft.refreshSec = next.refreshSec
  draft.kpiKeys = [...next.kpiKeys]
  draft.modules = next.modules.map((m) => ({ ...m }))
  ElMessage.success('已恢复默认布局配置')
}

function openPreview(blank = false) {
  if (!screen.menuEnabled) {
    ElMessage.info('当前为大屏关闭状态，仍可预览；开启后侧栏才会显示入口')
  }
  const href = router.resolve({ name: 'dashboard-screen', query: { preview: '1' } }).href
  if (blank) {
    window.open(href, '_blank')
    return
  }
  void router.push({ name: 'dashboard-screen', query: { preview: '1' } })
}

onMounted(() => {
  screen.ensureDefaults()
  screen.reloadLayout()
  syncDraftFromStore()
})
</script>

<template>
  <div v-if="!canManage" class="page">
    <el-empty description="无权访问大屏管理" />
  </div>
  <div v-else class="page">
    <section class="hero">
      <div class="hero-copy">
        <h2>大屏管理</h2>
        <p>控制系统侧栏「运营大屏」入口，并配置主题、布局模块与 KPI 指标（基于现有运营数据）。</p>
      </div>
      <div class="hero-actions">
        <el-button @click="openPreview(false)">预览大屏</el-button>
        <el-button type="primary" plain @click="openPreview(true)">新窗口预览</el-button>
      </div>
    </section>

    <el-card shadow="never" class="switch-card">
      <div class="switch-row">
        <div>
          <h3>运营大屏入口</h3>
          <p>关闭后，侧栏与 Dashboard 快捷入口将隐藏；管理页仍可预览与编辑配置。</p>
        </div>
        <el-switch
          :model-value="screen.menuEnabled"
          inline-prompt
          active-text="开启"
          inactive-text="关闭"
          @change="onMenuEnabledChange"
        />
      </div>
      <div class="status-chips">
        <el-tag :type="screen.menuEnabled ? 'success' : 'info'" effect="plain">
          菜单：{{ screen.menuEnabled ? '显示中' : '已隐藏' }}
        </el-tag>
        <el-tag type="info" effect="plain">主题：{{ screen.themeLabel }}</el-tag>
        <el-tag type="info" effect="plain">模块 {{ enabledModuleCount }} / {{ draft.modules.length }}</el-tag>
        <el-tag type="info" effect="plain">KPI {{ kpiCount }} 项</el-tag>
        <el-tag type="info" effect="plain">刷新 {{ draft.refreshSec }}s</el-tag>
      </div>
    </el-card>

    <el-card shadow="never" class="config-card">
      <template #header>
        <div class="card-header">
          <span>展示配置</span>
          <div class="actions">
            <el-button @click="handleReset">恢复默认</el-button>
            <el-button type="primary" :loading="saving" @click="handleSave">保存配置</el-button>
          </div>
        </div>
      </template>

      <el-form label-position="top" class="config-form">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="大屏标题">
              <el-input v-model="draft.title" maxlength="40" show-word-limit />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="自动刷新（秒）">
              <el-slider v-model="draft.refreshSec" :min="10" :max="120" :step="5" show-input />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">布局预设</el-divider>
        <div class="preset-grid">
          <button
            v-for="preset in layoutPresets"
            :key="preset.id"
            type="button"
            class="preset-card"
            @click="applyPreset(preset.id)"
          >
            <strong>{{ preset.label }}</strong>
            <small>{{ preset.description }}</small>
          </button>
        </div>

        <el-divider content-position="left">主题样式</el-divider>
        <div class="theme-grid">
          <button
            v-for="theme in SCREEN_THEMES"
            :key="theme.id"
            type="button"
            class="theme-card"
            :class="{ active: draft.theme === theme.id }"
            @click="setTheme(theme.id)"
          >
            <span class="theme-swatches">
              <i v-for="(c, i) in theme.preview" :key="i" :style="{ background: c }" />
            </span>
            <strong>{{ theme.label }}</strong>
            <small>{{ theme.description }}</small>
          </button>
        </div>

        <el-divider content-position="left">KPI 指标</el-divider>
        <p class="section-hint">对应大屏「核心指标」卡片，数据来自 Dashboard 汇总（数据中心/机房/机柜/设备/U 位/功耗等）。</p>
        <div class="kpi-grid">
          <el-checkbox
            v-for="opt in KPI_OPTIONS"
            :key="opt.key"
            :model-value="draft.kpiKeys.includes(opt.key)"
            @change="(v: boolean | string | number) => toggleKpi(opt.key, !!v)"
          >
            {{ opt.label }}<span v-if="opt.unit" class="unit">（{{ opt.unit }}）</span>
          </el-checkbox>
        </div>

        <el-divider content-position="left">布局模块</el-divider>
        <p class="section-hint">
          可拖拽卡片调整顺序；方向键按多列网格移动（←→ 相邻，↑↓ 换行）。保存后运营大屏立即生效。
        </p>
        <div class="mod-list">
          <div
            v-for="mod in sortedModules"
            :key="mod.id"
            class="mod-row"
            :class="{
              dragging: draggingModId === mod.id,
              'drag-over': dragOverModId === mod.id,
            }"
            :title="moduleDef(mod.id).description"
            draggable="true"
            @dragstart="onModDragStart(mod.id, $event)"
            @dragover="onModDragOver(mod.id, $event)"
            @drop="onModDrop(mod.id, $event)"
            @dragend="onModDragEnd"
          >
            <span class="mod-handle" title="拖拽排序">⠿</span>
            <el-checkbox v-model="mod.enabled" class="mod-check">
              <span class="mod-title">{{ moduleDef(mod.id).title }}</span>
            </el-checkbox>
            <div class="mod-ops">
              <el-select
                :model-value="mod.span"
                size="small"
                class="mod-span"
                @change="(v: ScreenSpan) => setSpan(mod.id, v)"
              >
                <el-option :value="1" label="1列" />
                <el-option :value="2" label="2列" />
                <el-option :value="3" label="整行" />
              </el-select>
              <div class="mod-pad" @click.stop>
                <button type="button" class="pad-btn pad-up" title="上移一行" @click="moveModule(mod.id, 'up')">↑</button>
                <button type="button" class="pad-btn pad-left" title="左移" @click="moveModule(mod.id, 'left')">←</button>
                <button type="button" class="pad-btn pad-right" title="右移" @click="moveModule(mod.id, 'right')">→</button>
                <button type="button" class="pad-btn pad-down" title="下移一行" @click="moveModule(mod.id, 'down')">↓</button>
              </div>
            </div>
          </div>
        </div>
      </el-form>
    </el-card>
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
  margin: 0 0 6px;
  font-size: 20px;
}

.hero-copy p {
  margin: 0;
  color: #607080;
  font-size: 13px;
}

.switch-card,
.config-card {
  border-radius: 12px;
}

.switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.switch-row h3 {
  margin: 0 0 4px;
  font-size: 16px;
}

.switch-row p {
  margin: 0;
  color: #607080;
  font-size: 13px;
}

.status-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.section-hint {
  margin: -4px 0 12px;
  color: #909399;
  font-size: 12px;
}

.preset-grid,
.theme-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
  margin-bottom: 8px;
}

.preset-card,
.theme-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.preset-card:hover,
.theme-card:hover,
.theme-card.active {
  border-color: #409eff;
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.2);
}

.preset-card strong,
.theme-card strong {
  font-size: 13px;
  color: #303133;
}

.preset-card small,
.theme-card small {
  color: #909399;
  font-size: 12px;
  line-height: 1.4;
}

.theme-swatches {
  display: flex;
  gap: 4px;
  margin-bottom: 4px;
}

.theme-swatches i {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  display: inline-block;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 6px 12px;
  margin-bottom: 8px;
}

.unit {
  color: #909399;
  font-size: 12px;
}

.mod-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 8px;
}

.mod-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-height: 40px;
  padding: 6px 8px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fafbfc;
  cursor: grab;
  transition: border-color 0.15s, box-shadow 0.15s, opacity 0.15s;
}

.mod-row:active {
  cursor: grabbing;
}

.mod-row.dragging {
  opacity: 0.55;
}

.mod-row.drag-over {
  border-color: #409eff;
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.35);
}

.mod-handle {
  flex-shrink: 0;
  width: 16px;
  color: #c0c4cc;
  font-size: 14px;
  line-height: 1;
  user-select: none;
}

.mod-check {
  flex: 1;
  min-width: 0;
}

.mod-title {
  display: inline-block;
  max-width: 96px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
  font-size: 13px;
}

.mod-ops {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.mod-span {
  width: 68px;
}

.mod-pad {
  display: grid;
  grid-template-columns: 22px 22px 22px;
  grid-template-rows: 20px 20px;
  gap: 2px;
  width: 70px;
}

.pad-btn {
  margin: 0;
  padding: 0;
  border: 1px solid #dcdfe6;
  border-radius: 3px;
  background: #fff;
  color: #606266;
  font-size: 11px;
  line-height: 18px;
  cursor: pointer;
}

.pad-btn:hover {
  color: #409eff;
  border-color: #a0cfff;
  background: #ecf5ff;
}

.pad-up {
  grid-column: 2;
  grid-row: 1;
}

.pad-left {
  grid-column: 1;
  grid-row: 2;
}

.pad-right {
  grid-column: 3;
  grid-row: 2;
}

.pad-down {
  grid-column: 2;
  grid-row: 2;
}

@media (min-width: 1200px) {
  .mod-list {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (min-width: 1600px) {
  .mod-list {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
</style>
