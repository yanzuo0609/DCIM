<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
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

const props = defineProps<{
  modelValue: boolean
  config: ScreenLayoutConfig
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  save: [config: ScreenLayoutConfig]
  reset: []
}>()

const draft = reactive<ScreenLayoutConfig>({
  version: 1,
  title: '',
  theme: 'teal',
  refreshSec: 30,
  kpiKeys: [],
  modules: [],
})

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    draft.title = props.config.title
    draft.theme = props.config.theme || 'teal'
    draft.refreshSec = props.config.refreshSec
    draft.kpiKeys = [...props.config.kpiKeys]
    draft.modules = props.config.modules.map((m) => ({ ...m }))
  },
  { immediate: true },
)

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

function toggleKpi(key: KpiKey, checked: boolean) {
  if (checked) {
    if (!draft.kpiKeys.includes(key)) draft.kpiKeys.push(key)
  } else {
    draft.kpiKeys = draft.kpiKeys.filter((k) => k !== key)
  }
}

function moveModule(id: string, dir: -1 | 1) {
  const list = [...draft.modules].sort((a, b) => a.order - b.order)
  const idx = list.findIndex((m) => m.id === id)
  const swap = idx + dir
  if (idx < 0 || swap < 0 || swap >= list.length) return
  const tmp = list[idx].order
  list[idx].order = list[swap].order
  list[swap].order = tmp
  draft.modules = list
}

function setSpan(id: string, span: ScreenSpan) {
  const row = draft.modules.find((m) => m.id === id)
  if (row) row.span = span
}

function setTheme(id: ScreenThemeId) {
  draft.theme = id
}

function onSave() {
  const modules = [...draft.modules]
    .sort((a, b) => a.order - b.order)
    .map((m, i) => ({ ...m, order: i }))
  emit('save', {
    version: 1,
    title: draft.title.trim() || '智慧机房管理驾驶舱',
    theme: draft.theme || 'teal',
    refreshSec: draft.refreshSec,
    kpiKeys: draft.kpiKeys.length ? draft.kpiKeys : (['device_count', 'utilization'] as KpiKey[]),
    modules,
  })
  visible.value = false
}
</script>

<template>
  <el-drawer v-model="visible" title="自定义大屏展示" size="420px" append-to-body>
    <el-form label-position="top">
      <el-form-item label="大屏标题">
        <el-input v-model="draft.title" maxlength="40" show-word-limit />
      </el-form-item>
      <el-form-item label="自动刷新（秒）">
        <el-slider v-model="draft.refreshSec" :min="10" :max="120" :step="5" show-input />
      </el-form-item>

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

      <el-divider content-position="left">KPI 指标（核心指标模块）</el-divider>
      <div class="kpi-grid">
        <el-checkbox
          v-for="opt in KPI_OPTIONS"
          :key="opt.key"
          :model-value="draft.kpiKeys.includes(opt.key)"
          @change="(v: boolean | string | number) => toggleKpi(opt.key, !!v)"
        >
          {{ opt.label }}
        </el-checkbox>
      </div>

      <el-divider content-position="left">展示模块</el-divider>
      <div class="mod-list">
        <div v-for="mod in [...draft.modules].sort((a, b) => a.order - b.order)" :key="mod.id" class="mod-row">
          <el-checkbox v-model="mod.enabled">{{ moduleDef(mod.id).title }}</el-checkbox>
          <div class="mod-ops">
            <el-select
              :model-value="mod.span"
              size="small"
              style="width: 88px"
              @change="(v: ScreenSpan) => setSpan(mod.id, v)"
            >
              <el-option :value="1" label="1 列" />
              <el-option :value="2" label="2 列" />
              <el-option :value="3" label="整行" />
            </el-select>
            <el-button-group>
              <el-button size="small" @click="moveModule(mod.id, -1)">上移</el-button>
              <el-button size="small" @click="moveModule(mod.id, 1)">下移</el-button>
            </el-button-group>
          </div>
          <p class="mod-desc">{{ moduleDef(mod.id).description }}</p>
        </div>
      </div>
    </el-form>

    <template #footer>
      <el-button @click="emit('reset')">恢复默认</el-button>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="onSave">保存并应用</el-button>
    </template>
  </el-drawer>
</template>

<style scoped>
.kpi-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 10px;
  margin-bottom: 8px;
}

.mod-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mod-row {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 10px;
}

.mod-ops {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.mod-desc {
  margin: 6px 0 0;
  font-size: 12px;
  color: #909399;
}

.theme-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 8px;
}

.theme-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 10px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.theme-card:hover {
  border-color: #a0cfff;
}

.theme-card.active {
  border-color: #409eff;
  box-shadow: 0 0 0 1px #409eff inset;
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
  display: block;
}

.theme-card strong {
  font-size: 13px;
  color: #303133;
}

.theme-card small {
  font-size: 11px;
  color: #909399;
  line-height: 1.3;
}
</style>
