<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { Rack } from '@/api/rack'

const props = withDefaults(
  defineProps<{
    racks: Rack[]
    modelValue: string[]
    /** 未选任何机柜时展示「全部」提示 */
    emptyMeansAll?: boolean
  }>(),
  { emptyMeansAll: true },
)

const emit = defineEmits<{
  'update:modelValue': [string[]]
}>()

const rangeText = ref('')
const rangeError = ref('')
const dragging = ref(false)
const dragMoved = ref(false)
const dragAnchor = ref<{ row: number; col: number } | null>(null)
const dragCurrent = ref<{ row: number; col: number } | null>(null)
const dragMode = ref<'replace' | 'add'>('replace')

const selectedSet = computed(() => new Set(props.modelValue))

const sortedRacks = computed(() =>
  [...props.racks].sort((a, b) =>
    a.code.localeCompare(b.code, undefined, { numeric: true, sensitivity: 'base' }),
  ),
)

const maxRow = computed(() => Math.max(1, ...props.racks.map((r) => r.row_no || 1)))
const maxCol = computed(() => Math.max(1, ...props.racks.map((r) => r.column_no || 1)))

const rackByPos = computed(() => {
  const map = new Map<string, Rack>()
  for (const rack of props.racks) {
    map.set(`${rack.row_no}-${rack.column_no}`, rack)
  }
  return map
})

const previewIds = computed(() => {
  if (!dragging.value || !dragAnchor.value || !dragCurrent.value) return null
  const r1 = Math.min(dragAnchor.value.row, dragCurrent.value.row)
  const r2 = Math.max(dragAnchor.value.row, dragCurrent.value.row)
  const c1 = Math.min(dragAnchor.value.col, dragCurrent.value.col)
  const c2 = Math.max(dragAnchor.value.col, dragCurrent.value.col)
  const ids: string[] = []
  for (let r = r1; r <= r2; r += 1) {
    for (let c = c1; c <= c2; c += 1) {
      const rack = rackByPos.value.get(`${r}-${c}`)
      if (rack) ids.push(rack.id)
    }
  }
  return ids
})

const displaySelected = computed(() => {
  if (previewIds.value) {
    if (dragMode.value === 'add') {
      return new Set([...props.modelValue, ...previewIds.value])
    }
    return new Set(previewIds.value)
  }
  return selectedSet.value
})

const selectedSummary = computed(() => {
  const ids = displaySelected.value
  if (!ids.size) return props.emptyMeansAll ? '未选择（将使用该机房全部机柜）' : '未选择'
  const codes = sortedRacks.value.filter((r) => ids.has(r.id)).map((r) => r.code)
  if (codes.length <= 6) return `已选 ${codes.length} 台：${codes.join('、')}`
  return `已选 ${codes.length} 台：${codes.slice(0, 4).join('、')} … ${codes[codes.length - 1]}`
})

watch(
  () => props.modelValue,
  (ids) => {
    if (dragging.value) return
    const codes = sortedRacks.value.filter((r) => ids.includes(r.id)).map((r) => r.code)
    if (!codes.length) {
      rangeText.value = ''
      return
    }
    if (codes.length === 1) {
      rangeText.value = codes[0]
      return
    }
    const allSorted = sortedRacks.value.map((r) => r.code)
    const start = allSorted.indexOf(codes[0])
    const end = allSorted.indexOf(codes[codes.length - 1])
    const slice = allSorted.slice(start, end + 1)
    const contiguous =
      start >= 0 && end >= start && slice.length === codes.length && slice.every((c, i) => c === codes[i])
    rangeText.value = contiguous ? `${codes[0]}-${codes[codes.length - 1]}` : codes.join(',')
  },
  { immediate: true },
)

/** 解析「A01-A10」「A01~A10」「A01,A02」等 */
function parseRackRangeText(text: string, racks: Rack[]): { ids: string[]; error?: string } {
  const raw = text.trim()
  if (!raw) return { ids: [] }

  const sorted = [...racks].sort((a, b) =>
    a.code.localeCompare(b.code, undefined, { numeric: true, sensitivity: 'base' }),
  )
  const ids = new Set<string>()
  const parts = raw.split(/[,，;；]/).map((s) => s.trim()).filter(Boolean)

  for (const part of parts) {
    const rangeMatch = part.match(/^(.+?)\s*[-~～—–到至]\s*(.+)$/)
    if (rangeMatch) {
      const startCode = rangeMatch[1].trim()
      const endCode = rangeMatch[2].trim()
      const startRack = sorted.find(
        (r) => r.code === startCode || r.code.toLowerCase() === startCode.toLowerCase(),
      )
      const endRack = sorted.find(
        (r) => r.code === endCode || r.code.toLowerCase() === endCode.toLowerCase(),
      )
      if (!startRack) return { ids: [], error: `起始机柜「${startCode}」不存在` }
      if (!endRack) return { ids: [], error: `结束机柜「${endCode}」不存在` }
      const i = sorted.findIndex((r) => r.id === startRack.id)
      const j = sorted.findIndex((r) => r.id === endRack.id)
      const from = Math.min(i, j)
      const to = Math.max(i, j)
      for (let k = from; k <= to; k += 1) ids.add(sorted[k].id)
      continue
    }

    const rack = sorted.find(
      (r) => r.code === part || r.code.toLowerCase() === part.toLowerCase(),
    )
    if (!rack) return { ids: [], error: `机柜「${part}」不存在` }
    ids.add(rack.id)
  }

  return { ids: sorted.filter((r) => ids.has(r.id)).map((r) => r.id) }
}

function applyRangeText() {
  const { ids, error } = parseRackRangeText(rangeText.value, props.racks)
  if (error) {
    rangeError.value = error
    return
  }
  rangeError.value = ''
  emit('update:modelValue', ids)
}

function clearSelection() {
  rangeError.value = ''
  rangeText.value = ''
  emit('update:modelValue', [])
}

function selectAll() {
  rangeError.value = ''
  emit(
    'update:modelValue',
    sortedRacks.value.map((r) => r.id),
  )
}

function isCellSelected(row: number, col: number) {
  const rack = rackByPos.value.get(`${row}-${col}`)
  if (!rack) return false
  return displaySelected.value.has(rack.id)
}

function emitSorted(ids: Iterable<string>) {
  const order = new Map(sortedRacks.value.map((r, i) => [r.id, i]))
  emit(
    'update:modelValue',
    [...ids].sort((a, b) => (order.get(a) ?? 0) - (order.get(b) ?? 0)),
  )
}

function onCellPointerDown(row: number, col: number, ev: PointerEvent) {
  const rack = rackByPos.value.get(`${row}-${col}`)
  if (!rack) return
  ev.preventDefault()
  dragging.value = true
  dragMoved.value = false
  dragMode.value = ev.ctrlKey || ev.metaKey ? 'add' : 'replace'
  dragAnchor.value = { row, col }
  dragCurrent.value = { row, col }
  window.addEventListener('pointerup', onPointerUp)
  window.addEventListener('pointercancel', onPointerUp)
}

function onCellPointerEnter(row: number, col: number) {
  if (!dragging.value || !dragAnchor.value) return
  if (row !== dragAnchor.value.row || col !== dragAnchor.value.col) {
    dragMoved.value = true
  }
  dragCurrent.value = { row, col }
}

function onPointerUp() {
  if (!dragging.value || !dragAnchor.value) return
  const anchor = dragAnchor.value
  const anchorRack = rackByPos.value.get(`${anchor.row}-${anchor.col}`)

  if (!dragMoved.value && anchorRack) {
    // 单击：切换该机柜选中状态
    const next = new Set(props.modelValue)
    if (next.has(anchorRack.id)) next.delete(anchorRack.id)
    else next.add(anchorRack.id)
    emitSorted(next)
  } else {
    const ids = previewIds.value || []
    if (dragMode.value === 'add') {
      emitSorted(new Set([...props.modelValue, ...ids]))
    } else {
      emitSorted(ids)
    }
  }

  dragging.value = false
  dragMoved.value = false
  dragAnchor.value = null
  dragCurrent.value = null
  rangeError.value = ''
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('pointercancel', onPointerUp)
}

onBeforeUnmount(() => {
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('pointercancel', onPointerUp)
})
</script>

<template>
  <div class="rack-range-picker">
    <div class="range-input-row">
      <el-input
        v-model="rangeText"
        clearable
        placeholder="输入范围，如 R0101-R0112 或 R0101,R0103"
        @keyup.enter="applyRangeText"
      />
      <el-button type="primary" plain @click="applyRangeText">应用</el-button>
      <el-button @click="selectAll">全选</el-button>
      <el-button @click="clearSelection">清空</el-button>
    </div>
    <p v-if="rangeError" class="range-error">{{ rangeError }}</p>
    <p class="range-hint">
      在下方机柜图按住拖选矩形范围；Ctrl/⌘ 拖选为追加。也可输入编号范围后点「应用」。
    </p>
    <p class="range-summary">{{ selectedSummary }}</p>

    <div v-if="!racks.length" class="grid-empty">当前机房暂无机柜</div>
    <div
      v-else
      class="rack-grid"
      :style="{ gridTemplateColumns: `repeat(${maxCol}, minmax(56px, 1fr))` }"
      @dragstart.prevent
    >
      <template v-for="row in maxRow" :key="`r-${row}`">
        <button
          v-for="col in maxCol"
          :key="`${row}-${col}`"
          type="button"
          class="rack-cell"
          :class="{
            empty: !rackByPos.get(`${row}-${col}`),
            selected: isCellSelected(row, col),
            dragging: dragging && isCellSelected(row, col),
          }"
          :disabled="!rackByPos.get(`${row}-${col}`)"
          :title="rackByPos.get(`${row}-${col}`)?.code || '空位'"
          @pointerdown="onCellPointerDown(row, col, $event)"
          @pointerenter="onCellPointerEnter(row, col)"
        >
          <span class="code">{{ rackByPos.get(`${row}-${col}`)?.code || '·' }}</span>
          <span v-if="rackByPos.get(`${row}-${col}`)" class="meta">
            空{{ rackByPos.get(`${row}-${col}`)!.free_u }}U
          </span>
        </button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.rack-range-picker {
  width: 100%;
}
.range-input-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.range-input-row .el-input {
  flex: 1;
  min-width: 220px;
}
.range-error {
  margin: 6px 0 0;
  color: var(--el-color-danger);
  font-size: 12px;
}
.range-hint {
  margin: 8px 0 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
}
.range-summary {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.grid-empty {
  padding: 24px;
  text-align: center;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light);
  border-radius: 6px;
}
.rack-grid {
  display: grid;
  gap: 6px;
  max-height: 320px;
  overflow: auto;
  padding: 8px;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  user-select: none;
  touch-action: none;
}
.rack-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-height: 48px;
  padding: 4px 2px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
  cursor: pointer;
  font: inherit;
  transition: background 0.12s, border-color 0.12s, color 0.12s;
}
.rack-cell:hover:not(:disabled) {
  border-color: var(--el-color-primary-light-3);
}
.rack-cell.empty {
  background: transparent;
  border-style: dashed;
  color: var(--el-text-color-placeholder);
  cursor: default;
}
.rack-cell.selected {
  background: var(--el-color-primary-light-8);
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
}
.rack-cell.dragging {
  background: var(--el-color-primary-light-7);
}
.rack-cell .code {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.2;
  word-break: break-all;
}
.rack-cell .meta {
  font-size: 10px;
  opacity: 0.75;
  line-height: 1;
}
</style>
