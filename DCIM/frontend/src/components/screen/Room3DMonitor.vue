<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  fetchDashboardRoomLayout,
  fetchDashboardRooms,
  type RoomMonitorLayout,
  type RoomMonitorOption,
  type RoomMonitorRack,
} from '@/api/dashboard'
import { getRackLayout, type Rack, type RackLayoutSlot } from '@/api/rack'
import RackCabinet from '@/components/RackCabinet.vue'

const props = withDefaults(
  defineProps<{
    /** cockpit：运营大屏深色；studio：管理端浅色仿真 */
    variant?: 'cockpit' | 'studio'
    /** 初始选中机房（优先于本地缓存） */
    preferredRoomId?: string | null
  }>(),
  {
    variant: 'cockpit',
    preferredRoomId: null,
  },
)

const emit = defineEmits<{
  stats: [
    payload: {
      roomId: string
      roomTitle: string
      deviceTotal: number
      danger: number
      fault: number
      occupied: number
      total: number
      avgUtil: number
      rackCount: number
    },
  ]
}>()

interface LayoutSlot {
  row: number
  col: number
  code: string
  rack: RoomMonitorRack | null
}

interface LayoutRow {
  row: number
  label: string
  slots: LayoutSlot[]
}

const STORAGE_KEY = 'dcim.cockpit.selectedRoomId'
const MIN_SCALE = 0.35
const MAX_SCALE = 3.2
const ZOOM_STEP = 1.12
const DRAG_THRESHOLD = 4
/** 适应窗口时四周留白（越小内容越大） */
const FIT_PAD_X = 28
const FIT_PAD_Y = 22

const router = useRouter()

const rooms = ref<RoomMonitorOption[]>([])
const layout = ref<RoomMonitorLayout | null>(null)
const selectedRoomId = ref('')
const selectedRackId = ref<string | null>(null)
const loadingRooms = ref(false)
const loadingLayout = ref(false)
const errorMsg = ref('')

const rackDialogVisible = ref(false)
const rackDialogLoading = ref(false)
const rackDialogError = ref('')
const rackDialogRack = ref<Rack | null>(null)
const rackDialogSlots = ref<RackLayoutSlot[]>([])
const rackDialogPower = ref(0)

const stageRef = ref<HTMLElement | null>(null)
const floorRef = ref<HTMLElement | null>(null)
const scale = ref(1)
const offsetX = ref(0)
const offsetY = ref(0)
const dragging = ref(false)

let pointerId: number | null = null
let dragStartX = 0
let dragStartY = 0
let originOffsetX = 0
let originOffsetY = 0
let dragMoved = false
let suppressClick = false
let pointerDownOnUi = false

const roomOptions = computed(() =>
  rooms.value.map((r) => ({
    id: r.id,
    label:
      [r.datacenter_name, r.name].filter(Boolean).join(' / ') +
      (r.rack_count ? `（${r.rack_count}柜）` : ''),
  })),
)

const layoutRows = computed<LayoutRow[]>(() => {
  const data = layout.value
  if (!data) return []

  let rows: number[] =
    data.row_layout?.length > 0
      ? [...data.row_layout]
      : Array.from({ length: Math.max(data.rack_rows, 0) }, () => data.rack_columns || 0)

  for (const rack of data.racks) {
    while (rows.length < rack.row_no) {
      rows.push(Math.max(data.rack_columns || 1, 1))
    }
    const idx = rack.row_no - 1
    if (idx >= 0 && rows[idx] < rack.column_no) {
      rows[idx] = rack.column_no
    }
  }

  if (!rows.length && data.racks.length) {
    const maxRow = Math.max(...data.racks.map((r) => r.row_no))
    const maxCol = Math.max(...data.racks.map((r) => r.column_no))
    rows = Array.from({ length: maxRow }, () => maxCol)
  }

  const codes = data.slot_codes || []
  const rackMap = new Map(data.racks.map((r) => [`${r.row_no}-${r.column_no}`, r]))

  return rows.map((cols, idx) => {
    const row = idx + 1
    const slots: LayoutSlot[] = Array.from({ length: cols }, (_, colIdx) => {
      const col = colIdx + 1
      const code =
        codes[idx]?.[colIdx] ||
        `R${String(row).padStart(2, '0')}${String(col).padStart(2, '0')}`
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
  const occupiedSlots = layoutRows.value.flatMap((r) => r.slots).filter((s) => s.rack)
  const occupied = occupiedSlots.length
  const avgUtil =
    occupied === 0
      ? 0
      : Math.round(
          occupiedSlots.reduce((sum, s) => sum + (s.rack?.utilization || 0), 0) / occupied,
        )
  return {
    total,
    occupied,
    free: total - occupied,
    avgUtil,
    rackCount: layout.value?.racks.length || 0,
  }
})

const selectedSlot = computed(() => {
  for (const row of layoutRows.value) {
    for (const slot of row.slots) {
      if (slot.rack?.id === selectedRackId.value) return slot
    }
  }
  return null
})

const maxCols = computed(() =>
  layoutRows.value.reduce((max, row) => Math.max(max, row.slots.length), 0),
)

const viewportStyle = computed(() => ({
  transform: `translate3d(${offsetX.value}px, ${offsetY.value}px, 0) scale(${scale.value})`,
}))

const scalePercent = computed(() => `${Math.round(scale.value * 100)}%`)

function utilTone(util: number) {
  if (util >= 85) return 'hot'
  if (util >= 60) return 'warm'
  return 'ok'
}

function isAlarmRack(rack: RoomMonitorRack | null | undefined) {
  if (!rack) return false
  if ((rack.utilization || 0) >= 85) return true
  const st = (rack.status || '').toLowerCase()
  return st.includes('fault') || st.includes('error') || st.includes('故障') || st === 'alarm'
}

function clampScale(value: number) {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, value))
}

async function resetView() {
  const stage = stageRef.value
  scale.value = 1
  offsetX.value = 0
  offsetY.value = 0
  if (!stage || !layoutRows.value.length) return
  await nextTick()
  await waitFrames(1)
  const floor = floorRef.value
  if (!floor) return
  const stageRect = stage.getBoundingClientRect()
  const measured = floor.getBoundingClientRect()
  if (measured.width < 4) return
  // 超出舞台则自动适应，否则仅居中
  if (
    measured.width > stageRect.width - FIT_PAD_X * 2 ||
    measured.height > stageRect.height - FIT_PAD_Y * 2
  ) {
    await fitView()
    return
  }
  const stageCx = stageRect.left + stageRect.width / 2
  const stageCy = stageRect.top + stageRect.height / 2
  const contentCx = (measured.left + measured.right) / 2
  const contentCy = (measured.top + measured.bottom) / 2
  offsetX.value = stageCx - contentCx
  offsetY.value = stageCy - contentCy
}

function waitFrames(n = 2) {
  return new Promise<void>((resolve) => {
    const step = (left: number) => {
      if (left <= 0) {
        resolve()
        return
      }
      requestAnimationFrame(() => step(left - 1))
    }
    step(n)
  })
}

/** 按实际包围盒放大并居中，尽量填满可视区 */
async function fitView() {
  const rows = layoutRows.value.length
  const cols = maxCols.value
  const stage = stageRef.value
  if (!rows || !cols || !stage) {
    resetView()
    return
  }

  // 先复位，再量真实投影尺寸
  scale.value = 1
  offsetX.value = 0
  offsetY.value = 0
  await nextTick()
  await waitFrames(2)

  const floor = floorRef.value
  const stageRect = stage.getBoundingClientRect()
  let contentW = 0
  let contentH = 0

  if (floor) {
    const floorRect = floor.getBoundingClientRect()
    contentW = floorRect.width
    contentH = floorRect.height
  }

  // DOM 尚未就绪时退回估算
  if (contentW < 8 || contentH < 8) {
    contentW = cols * 52 + 64
    contentH = rows * 72 + 48
  }

  const availW = Math.max(stageRect.width - FIT_PAD_X * 2, 48)
  const availH = Math.max(stageRect.height - FIT_PAD_Y * 2, 48)
  const nextScale = clampScale(Math.min(availW / contentW, availH / contentH))
  scale.value = nextScale

  await nextTick()
  await waitFrames(1)

  // 缩放后按包围盒中心对齐舞台中心
  const measured = floorRef.value?.getBoundingClientRect()
  if (measured && measured.width > 4) {
    const stageCx = stageRect.left + stageRect.width / 2
    const stageCy = stageRect.top + stageRect.height / 2
    const contentCx = (measured.left + measured.right) / 2
    const contentCy = (measured.top + measured.bottom) / 2
    offsetX.value += stageCx - contentCx
    offsetY.value += stageCy - contentCy
  } else {
    offsetX.value = 0
    offsetY.value = 0
  }
}

function zoomBy(factor: number, centerX?: number, centerY?: number) {
  const stage = stageRef.value
  const prev = scale.value
  const next = clampScale(prev * factor)
  if (next === prev) return

  if (stage && centerX != null && centerY != null) {
    const rect = stage.getBoundingClientRect()
    const cx = centerX - rect.left - rect.width / 2
    const cy = centerY - rect.top - rect.height / 2
    // 以指针为锚点缩放，保持落点相对稳定
    offsetX.value = cx - ((cx - offsetX.value) * next) / prev
    offsetY.value = cy - ((cy - offsetY.value) * next) / prev
  }
  scale.value = next
}

function zoomIn() {
  zoomBy(ZOOM_STEP)
}

function zoomOut() {
  zoomBy(1 / ZOOM_STEP)
}

function onWheel(event: WheelEvent) {
  event.preventDefault()
  const factor = event.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP
  zoomBy(factor, event.clientX, event.clientY)
}

function isUiChrome(target: EventTarget | null) {
  const el = target as HTMLElement | null
  return !!el?.closest?.(
    '.tip, .tip-card, .rack-dialog-mask, .view-tools, .room-select, .tool-btn, .toolbar, .legend',
  )
}

function rackFromPoint(clientX: number, clientY: number): RoomMonitorRack | null {
  const stage = stageRef.value
  if (!stage || !layout.value) return null
  const hits = document.elementsFromPoint(clientX, clientY)
  for (const node of hits) {
    const btn = (node as HTMLElement).closest?.('button.slot') as HTMLButtonElement | null
    if (!btn || btn.disabled || !stage.contains(btn)) continue
    const id = btn.dataset.rackId
    if (!id) continue
    return layout.value.racks.find((r) => r.id === id) || null
  }
  return null
}

function onPointerDown(event: PointerEvent) {
  if (event.button !== 0) return
  pointerDownOnUi = isUiChrome(event.target)
  if (pointerDownOnUi) return

  // 点在机柜上：不启动拖拽，交给 pointerup / click 选中
  const onSlot = !!(event.target as HTMLElement | null)?.closest?.('button.slot:not(:disabled)')
  if (onSlot) {
    pointerId = null
    dragging.value = false
    dragMoved = false
    suppressClick = false
    return
  }

  pointerId = event.pointerId
  dragging.value = true
  dragMoved = false
  suppressClick = false
  dragStartX = event.clientX
  dragStartY = event.clientY
  originOffsetX = offsetX.value
  originOffsetY = offsetY.value
  stageRef.value?.setPointerCapture?.(event.pointerId)
  event.preventDefault()
}

function onPointerMove(event: PointerEvent) {
  if (!dragging.value || pointerId !== event.pointerId) return
  const dx = event.clientX - dragStartX
  const dy = event.clientY - dragStartY
  if (!dragMoved && Math.hypot(dx, dy) >= DRAG_THRESHOLD) {
    dragMoved = true
    suppressClick = true
  }
  if (!dragMoved) return
  offsetX.value = originOffsetX + dx
  offsetY.value = originOffsetY + dy
}

function onPointerUp(event: PointerEvent) {
  const wasDragging = dragging.value && pointerId === event.pointerId
  const moved = dragMoved
  const blocked = suppressClick

  if (wasDragging) {
    dragging.value = false
    pointerId = null
    try {
      stageRef.value?.releasePointerCapture?.(event.pointerId)
    } catch {
      /* ignore */
    }
  }

  // 未拖拽时：用命中测试选中机柜（兼容 3D 变换下 click 丢失）
  if (!pointerDownOnUi && !moved && !blocked && !slotGestureHandled) {
    const rack = rackFromPoint(event.clientX, event.clientY)
    if (rack) selectRack(rack)
  }

  dragMoved = false
  suppressClick = false
  pointerDownOnUi = false
}

function onPointerCancel(event: PointerEvent) {
  if (pointerId !== event.pointerId) return
  dragging.value = false
  pointerId = null
  dragMoved = false
  suppressClick = false
  pointerDownOnUi = false
}

function selectRack(rack: RoomMonitorRack | null) {
  if (!rack) return
  // 再次点击同一机柜：打开布局图，保证有明确反馈
  if (selectedRackId.value === rack.id) {
    void openRackLayoutDialog(rack)
    return
  }
  selectedRackId.value = rack.id
}

/** 同一手势内 pointerup 已处理后，忽略随后的 click，避免“一点就弹窗” */
let slotGestureHandled = false

function onSlotPointerUp(rack: RoomMonitorRack | null, event: PointerEvent) {
  event.preventDefault()
  event.stopPropagation()
  if (event.button !== 0 && event.button !== -1) return
  suppressClick = false
  dragMoved = false
  slotGestureHandled = true
  selectRack(rack)
  window.setTimeout(() => {
    slotGestureHandled = false
  }, 0)
}

function onSlotClick(rack: RoomMonitorRack | null, event: MouseEvent) {
  event.preventDefault()
  event.stopPropagation()
  if (slotGestureHandled) return
  suppressClick = false
  dragMoved = false
  selectRack(rack)
}

async function openRackLayoutDialog(rack?: RoomMonitorRack | null) {
  const target = rack || selectedSlot.value?.rack
  if (!target) return
  selectedRackId.value = target.id
  rackDialogVisible.value = true
  rackDialogLoading.value = true
  rackDialogError.value = ''
  rackDialogRack.value = null
  rackDialogSlots.value = []
  rackDialogPower.value = 0
  try {
    const data = await getRackLayout(target.id)
    rackDialogRack.value = data.rack
    rackDialogSlots.value = data.slots || []
    rackDialogPower.value = data.total_power || 0
  } catch (e) {
    rackDialogError.value = e instanceof Error ? e.message : '加载机柜布局失败'
  } finally {
    rackDialogLoading.value = false
  }
}

function goRoomManageLayout() {
  const rack = selectedSlot.value?.rack || rackDialogRack.value
  if (!selectedRoomId.value || !rack) return
  void router.push({
    name: 'rooms-manage',
    query: {
      open_layout: selectedRoomId.value,
      rack_id: rack.id,
    },
  })
}

async function loadAllRooms() {
  loadingRooms.value = true
  errorMsg.value = ''
  try {
    const all = await fetchDashboardRooms()
    rooms.value = all
    const saved = localStorage.getItem(STORAGE_KEY)
    const fromProp = props.preferredRoomId
    const preferred =
      (fromProp && all.find((r) => r.id === fromProp)?.id) ||
      (saved && all.find((r) => r.id === saved)?.id) ||
      all.find((r) => r.rack_count > 0)?.id ||
      all[0]?.id ||
      ''
    if (preferred && preferred !== selectedRoomId.value) {
      selectedRoomId.value = preferred
    } else if (!preferred) {
      selectedRoomId.value = ''
      layout.value = null
    } else if (preferred === selectedRoomId.value) {
      await loadRoomLayout(preferred)
    }
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '加载机房失败'
    rooms.value = []
  } finally {
    loadingRooms.value = false
  }
}

async function loadRoomLayout(roomId: string) {
  if (!roomId) {
    layout.value = null
    selectedRackId.value = null
    return
  }
  loadingLayout.value = true
  errorMsg.value = ''
  try {
    const data = await fetchDashboardRoomLayout(roomId)
    layout.value = data
    // 不默认选中，避免“已有 tip、再点无感”；由用户点击触发
    if (!data.racks.some((r) => r.id === selectedRackId.value)) {
      selectedRackId.value = null
    }
    await nextTick()
    await fitView()
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '加载机柜布局失败'
    layout.value = null
    selectedRackId.value = null
  } finally {
    loadingLayout.value = false
  }
}

watch(selectedRoomId, (id) => {
  if (id) localStorage.setItem(STORAGE_KEY, id)
  void loadRoomLayout(id)
})

let resizeObserver: ResizeObserver | null = null
let fitTimer: number | undefined

function scheduleFit() {
  if (fitTimer) window.clearTimeout(fitTimer)
  fitTimer = window.setTimeout(() => {
    if (layoutRows.value.length) void fitView()
  }, 120)
}

onMounted(() => {
  void loadAllRooms()
  resizeObserver = new ResizeObserver(() => scheduleFit())
  nextTick(() => {
    if (stageRef.value) resizeObserver?.observe(stageRef.value)
  })
})

watch(stageRef, (el, prev) => {
  if (prev) resizeObserver?.unobserve(prev)
  if (el) resizeObserver?.observe(el)
})

onBeforeUnmount(() => {
  dragging.value = false
  pointerId = null
  if (fitTimer) window.clearTimeout(fitTimer)
  resizeObserver?.disconnect()
  resizeObserver = null
})

function emitStats() {
  const data = layout.value
  const racks = data?.racks || []
  const deviceTotal = racks.reduce((s, r) => s + (r.device_count || 0), 0)
  const danger = racks.filter((r) => (r.utilization || 0) >= 85).length
  const fault = racks.filter((r) => {
    const st = (r.status || '').toLowerCase()
    return st.includes('fault') || st.includes('error') || st.includes('故障') || st === 'alarm'
  }).length
  emit('stats', {
    roomId: selectedRoomId.value,
    roomTitle:
      [data?.datacenter_name, data?.location, data?.room_name].filter(Boolean).join(' / ') ||
      '3D 机房仿真',
    deviceTotal,
    danger,
    fault,
    occupied: layoutStats.value.occupied,
    total: layoutStats.value.total,
    avgUtil: layoutStats.value.avgUtil,
    rackCount: layoutStats.value.rackCount,
  })
}

watch([layout, layoutStats, selectedRoomId], () => emitStats(), { deep: true })

watch(
  () => props.preferredRoomId,
  (id) => {
    if (!id || id === selectedRoomId.value) return
    selectedRoomId.value = id
    localStorage.setItem(STORAGE_KEY, id)
  },
)

defineExpose({
  reload: async () => {
    await loadAllRooms()
  },
  fitView,
  selectedRoomId,
  layout,
  layoutStats,
})
</script>

<template>
  <div class="monitor" :class="[`variant-${variant}`]">
    <header class="toolbar">
      <div class="title-wrap">
        <h3 class="panel-title">{{ variant === 'studio' ? '三维仿真视图' : '机房三维监控' }}</h3>
        <p v-if="layout" class="sub">
          {{ layout.location || layout.room_name }}
          · {{ layoutStats.occupied }}/{{ layoutStats.total }} 位
          · 均利用率 {{ layoutStats.avgUtil }}%
        </p>
      </div>
      <div class="controls">
        <label class="room-select">
          <span>机房</span>
          <select v-model="selectedRoomId" :disabled="loadingRooms || !rooms.length">
            <option v-if="!rooms.length" value="">暂无机房</option>
            <option v-for="opt in roomOptions" :key="opt.id" :value="opt.id">
              {{ opt.label }}
            </option>
          </select>
        </label>
        <div class="view-tools" aria-label="视图控制">
          <button type="button" class="tool-btn" title="缩小" @click="zoomOut">−</button>
          <span class="scale-label">{{ scalePercent }}</span>
          <button type="button" class="tool-btn" title="放大" @click="zoomIn">+</button>
          <button type="button" class="tool-btn wide" title="适应窗口" @click="fitView">适应</button>
          <button type="button" class="tool-btn wide" title="重置视图" @click="resetView">复位</button>
        </div>
      </div>
    </header>

    <div
      ref="stageRef"
      class="stage"
      :class="{ loading: loadingLayout || loadingRooms, dragging }"
      @wheel.prevent="onWheel"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerCancel"
    >
      <p v-if="errorMsg" class="hint error">{{ errorMsg }}</p>
      <p v-else-if="!selectedRoomId" class="hint">请选择机房</p>
      <p v-else-if="!layoutRows.length" class="hint">该机房尚未配置机柜布局</p>
      <div
        v-else
        class="iso-scene"
        :style="{ '--cols': String(Math.max(maxCols, 1)) }"
      >
        <div class="iso-viewport" :style="viewportStyle">
          <div ref="floorRef" class="iso-floor">
            <div
              v-for="row in layoutRows"
              :key="row.row"
              class="iso-row-group"
            >
              <div class="iso-row">
                <div class="row-tag">{{ row.label }}</div>
                <div class="iso-slots">
                  <button
                    v-for="slot in row.slots"
                    :key="`${slot.row}-${slot.col}`"
                    type="button"
                    class="slot"
                    :class="[
                      slot.rack ? utilTone(slot.rack.utilization) : 'empty',
                      {
                        active: slot.rack?.id === selectedRackId,
                        occupied: !!slot.rack,
                        alarm: isAlarmRack(slot.rack),
                      },
                    ]"
                    :data-rack-id="slot.rack?.id || undefined"
                    :disabled="!slot.rack"
                    :title="
                      slot.rack
                        ? `${slot.rack.code} · ${slot.rack.name} · ${slot.rack.utilization}%`
                        : `${slot.code}（空位）`
                    "
                    @click.stop="onSlotClick(slot.rack, $event)"
                    @pointerdown.stop
                    @pointerup.stop="onSlotPointerUp(slot.rack, $event)"
                  >
                    <span class="rack-body">
                      <span class="rack-shadow" />
                      <span class="rack-top" />
                      <span class="rack-side" />
                      <span class="rack-front">
                        <span class="rack-bezel" />
                        <span class="rack-mesh">
                          <i v-for="n in 10" :key="n" class="u-line" />
                          <span
                            v-for="led in 5"
                            :key="`led-${led}`"
                            class="mesh-led"
                            :style="{ top: `${10 + led * 14}%`, left: led % 2 === 0 ? '18%' : '62%' }"
                          />
                        </span>
                        <span class="rack-foot" />
                      </span>
                      <span v-if="isAlarmRack(slot.rack)" class="rack-alarm" title="告警" />
                    </span>
                    <span class="slot-code">{{ slot.rack?.code || slot.code }}</span>
                  </button>
                </div>
              </div>
              <div class="aisle-vent" aria-hidden="true" />
            </div>
          </div>
        </div>

        <div v-if="selectedSlot?.rack" class="tip">
          <div class="reticle" />
          <div class="tip-card">
            <strong>{{ selectedSlot.rack.code }}</strong>
            <span>{{ selectedSlot.rack.name }}</span>
            <span>位置 第{{ selectedSlot.row }}排 / 第{{ selectedSlot.col }}列</span>
            <span>状态 {{ selectedSlot.rack.status || '—' }}</span>
            <span>利用率 {{ selectedSlot.rack.utilization }}%</span>
            <span>
              {{ selectedSlot.rack.occupied_u }}/{{ selectedSlot.rack.total_u }}U ·
              {{ selectedSlot.rack.device_count }} 台设备
            </span>
            <div class="tip-actions">
              <button type="button" class="tip-btn primary" @click.stop="openRackLayoutDialog()">
                查看布局图
              </button>
              <button type="button" class="tip-btn" @click.stop="goRoomManageLayout">
                机房管理中打开
              </button>
            </div>
          </div>
        </div>

        <p class="gesture-hint">
          滚轮缩放 · 拖拽平移 · 点击机柜查看信息 · 再点同一机柜打开布局图
        </p>
      </div>
    </div>

    <footer class="legend">
      <span><i class="dot ok" />正常</span>
      <span><i class="dot warm" />偏高</span>
      <span><i class="dot hot" />告警</span>
      <span><i class="dot empty" />空位</span>
    </footer>

    <div v-if="rackDialogVisible" class="rack-dialog-mask" @click.self="rackDialogVisible = false">
      <div class="rack-dialog" role="dialog" aria-modal="true">
        <header class="rack-dialog-head">
          <div>
            <h4>{{ rackDialogRack?.code || selectedSlot?.rack?.code || '机柜布局' }}</h4>
            <p v-if="rackDialogRack || selectedSlot?.rack">
              {{ rackDialogRack?.name || selectedSlot?.rack?.name }}
              · 第{{ selectedSlot?.row }}排 / 第{{ selectedSlot?.col }}列
            </p>
          </div>
          <button type="button" class="tool-btn" @click="rackDialogVisible = false">关闭</button>
        </header>
        <div v-if="rackDialogLoading" class="rack-dialog-body loading">加载机柜布局…</div>
        <div v-else-if="rackDialogError" class="rack-dialog-body error">{{ rackDialogError }}</div>
        <div v-else-if="rackDialogRack" class="rack-dialog-body">
          <div class="rack-dialog-meta">
            <span>已用 {{ rackDialogRack.occupied_u }}/{{ rackDialogRack.total_u }}U</span>
            <span>空闲 {{ rackDialogRack.free_u }}U</span>
            <span>利用率 {{ rackDialogRack.utilization }}%</span>
            <span>设备 {{ rackDialogRack.device_count }} 台</span>
            <span>功率 {{ Math.round(rackDialogPower) }} W</span>
          </div>
          <div class="rack-dialog-cabinet">
            <RackCabinet
              :code="rackDialogRack.code"
              :total-u="rackDialogRack.total_u"
              :slots="rackDialogSlots"
              :total-power="rackDialogPower"
              :visual-style="(rackDialogRack.visual_style as any) || 'classic'"
            />
          </div>
        </div>
        <footer class="rack-dialog-foot">
          <button type="button" class="tip-btn" @click="goRoomManageLayout">机房管理中打开</button>
          <button type="button" class="tip-btn primary" @click="rackDialogVisible = false">完成</button>
        </footer>
      </div>
    </div>
  </div>
</template>

<style scoped>
.monitor {
  display: flex;
  flex-direction: column;
  gap: 8px;
  height: 100%;
  min-height: 0;
}

.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.title-wrap {
  min-width: 0;
}

.panel-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--accent, #9fe8d8);
}

.sub {
  margin: 4px 0 0;
  font-size: 11px;
  color: rgba(170, 205, 215, 0.72);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.controls {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.room-select {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: rgba(170, 205, 215, 0.85);
}

.room-select select {
  min-width: 160px;
  max-width: 260px;
  height: 28px;
  border-radius: 6px;
  border: 1px solid rgba(64, 180, 190, 0.45);
  background: rgba(6, 22, 32, 0.9);
  color: #e7f4f1;
  padding: 0 8px;
  outline: none;
}

.room-select select:focus {
  border-color: #1ec8a5;
}

.view-tools {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.tool-btn {
  height: 28px;
  min-width: 28px;
  padding: 0 8px;
  border-radius: 6px;
  border: 1px solid rgba(64, 180, 190, 0.45);
  background: rgba(6, 22, 32, 0.9);
  color: #e7f4f1;
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
}

.tool-btn.wide {
  min-width: 44px;
  font-size: 12px;
}

.tool-btn:hover {
  border-color: #1ec8a5;
  color: #9fe8d8;
}

.scale-label {
  min-width: 42px;
  text-align: center;
  font-size: 11px;
  color: rgba(170, 205, 215, 0.85);
  font-variant-numeric: tabular-nums;
}

.stage {
  position: relative;
  flex: 1;
  min-height: 280px;
  border: 1px solid color-mix(in srgb, var(--accent, #1ec8a5) 45%, transparent);
  border-radius: 10px;
  background:
    radial-gradient(ellipse at 50% 0%, color-mix(in srgb, var(--accent, #1ec8a5) 14%, transparent), transparent 55%),
    linear-gradient(180deg, rgba(12, 36, 48, 0.55), rgba(6, 16, 26, 0.75));
  overflow: hidden;
  display: grid;
  place-items: center;
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.stage.dragging {
  cursor: grabbing;
}

.stage.loading {
  opacity: 0.72;
}

.hint {
  margin: 0;
  color: rgba(170, 205, 215, 0.72);
  font-size: 13px;
}

.hint.error {
  color: #e35d5b;
}

.iso-scene {
  position: relative;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  perspective: 1100px;
  overflow: hidden;
}

.iso-viewport {
  position: absolute;
  left: 50%;
  top: 50%;
  transform-origin: center center;
  will-change: transform;
}


.iso-floor {
  width: max-content;
  margin-left: -50%;
  margin-top: -50%;
  /* 仅俯仰，不旋转 Z，机柜排保持屏幕横向水平 */
  transform: rotateX(58deg);
  transform-style: preserve-3d;
  display: flex;
  flex-direction: column;
  gap: 22px;
  padding: 18px 24px 28px;
  pointer-events: none;
}

.iso-row-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  transform-style: preserve-3d;
}

.iso-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  transform-style: preserve-3d;
}

.row-tag {
  width: 42px;
  text-align: right;
  font-size: 10px;
  color: rgba(158, 220, 210, 0.75);
  transform: rotateX(-58deg);
  transform-origin: right center;
  white-space: nowrap;
  flex-shrink: 0;
  pointer-events: none;
  margin-bottom: 28px;
}

.iso-slots {
  display: flex;
  gap: 2px;
  transform-style: preserve-3d;
}

.aisle-vent {
  margin-left: 50px;
  height: 14px;
  border-radius: 2px;
  background:
    radial-gradient(circle, rgba(40, 48, 58, 0.55) 1.1px, transparent 1.3px) 0 0 / 5px 5px,
    linear-gradient(180deg, #9aa3ad, #7d8792);
  border: 1px solid rgba(80, 90, 100, 0.35);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15);
  opacity: 0.85;
}

.slot {
  width: 32px;
  height: 78px;
  border: none;
  background: transparent;
  padding: 0;
  position: relative;
  cursor: pointer;
  transform-style: preserve-3d;
  transform: rotateX(-58deg);
  transform-origin: bottom center;
  pointer-events: auto;
  z-index: 2;
}

.slot::before {
  content: '';
  position: absolute;
  inset: -8px -10px -12px -10px;
  z-index: 3;
}

.slot:disabled {
  cursor: inherit;
  pointer-events: none;
}

.slot:disabled::before {
  display: none;
}

.rack-body {
  position: absolute;
  inset: 0;
  transform-style: preserve-3d;
  pointer-events: none;
}

.rack-shadow {
  position: absolute;
  left: 1px;
  right: 1px;
  bottom: -5px;
  height: 8px;
  border-radius: 50%;
  background: radial-gradient(ellipse at center, rgba(20, 28, 40, 0.32), transparent 72%);
  z-index: 0;
}

.rack-front,
.rack-side,
.rack-top {
  position: absolute;
  display: block;
}

.rack-top {
  left: 0;
  top: -7px;
  width: 100%;
  height: 7px;
  background: linear-gradient(90deg, #3a3d42 0%, #2b2d31 50%, #1e2024 100%);
  border: 1px solid rgba(0, 0, 0, 0.4);
  border-bottom: none;
  transform: skewX(-28deg);
  transform-origin: bottom left;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
  z-index: 1;
}

.rack-side {
  top: 1px;
  right: -7px;
  width: 7px;
  height: calc(100% - 1px);
  background: linear-gradient(180deg, #25282c 0%, #16181b 60%, #0f1012 100%);
  border: 1px solid rgba(0, 0, 0, 0.45);
  border-left: none;
  transform: skewY(-18deg);
  transform-origin: left top;
  z-index: 1;
}

.rack-front {
  inset: 0;
  border-radius: 2px 2px 1px 1px;
  background: linear-gradient(180deg, #32353a 0%, #22252a 45%, #1a1c20 100%);
  border: 1px solid #0c0d0f;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.05),
    0 3px 10px rgba(0, 0, 0, 0.28);
  overflow: hidden;
  z-index: 2;
}

.rack-bezel {
  position: absolute;
  inset: 0;
  border: 2px solid #1a1c1f;
  border-radius: 1px;
  box-shadow: inset 0 0 0 1px rgba(70, 76, 84, 0.4);
  pointer-events: none;
  z-index: 3;
}

.rack-mesh {
  position: absolute;
  left: 3px;
  right: 3px;
  top: 4px;
  bottom: 6px;
  border-radius: 1px;
  background-color: #1b1e22;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    repeating-linear-gradient(
      180deg,
      rgba(55, 60, 68, 0.55) 0 3px,
      rgba(18, 20, 24, 0.9) 3px 5px
    );
  background-size: 3px 3px, 3px 3px, 100% 5px;
  border: 1px solid rgba(0, 0, 0, 0.55);
  box-shadow:
    inset 0 0 10px rgba(0, 0, 0, 0.55),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  display: flex;
  flex-direction: column;
  justify-content: space-evenly;
  padding: 4px 3px;
  overflow: hidden;
  z-index: 2;
}

.rack-mesh .u-line {
  display: block;
  height: 2px;
  border-radius: 1px;
  background: rgba(90, 98, 110, 0.35);
  position: relative;
  z-index: 1;
}

.mesh-led {
  position: absolute;
  width: 3px;
  height: 3px;
  border-radius: 1px;
  background: #4ade80;
  box-shadow: 0 0 4px rgba(74, 222, 128, 0.95);
  z-index: 4;
}

.rack-foot {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 4px;
  background: linear-gradient(180deg, #2e3136, #121416);
  border-top: 1px solid rgba(0, 0, 0, 0.5);
  z-index: 4;
}

.rack-alarm {
  position: absolute;
  left: 50%;
  top: -20px;
  width: 12px;
  height: 12px;
  margin-left: -6px;
  background: #e53935;
  transform: rotate(45deg);
  box-shadow:
    0 0 0 2px rgba(255, 255, 255, 0.9),
    0 0 8px rgba(229, 57, 53, 0.7);
  z-index: 6;
  animation: alarm-pulse 1.4s ease-in-out infinite;
}

.rack-alarm::after {
  content: '!';
  position: absolute;
  inset: 0;
  transform: rotate(-45deg);
  color: #fff;
  font-size: 8px;
  font-weight: 800;
  line-height: 12px;
  text-align: center;
}

@keyframes alarm-pulse {
  0%,
  100% {
    opacity: 1;
    filter: brightness(1);
  }
  50% {
    opacity: 0.72;
    filter: brightness(1.25);
  }
}

.slot.empty .rack-front {
  background: rgba(255, 255, 255, 0.4);
  border: 1px dashed rgba(140, 160, 180, 0.55);
  box-shadow: none;
}

.slot.empty .rack-bezel,
.slot.empty .rack-mesh,
.slot.empty .rack-foot,
.slot.empty .rack-alarm {
  display: none;
}

.slot.empty .rack-side,
.slot.empty .rack-top,
.slot.empty .rack-shadow {
  opacity: 0.18;
}

.slot.ok .mesh-led {
  background: #4ade80;
  box-shadow: 0 0 4px rgba(74, 222, 128, 0.95);
}

.slot.warm .mesh-led {
  background: #f0b429;
  box-shadow: 0 0 4px rgba(240, 180, 41, 0.95);
}

.slot.warm .rack-front {
  box-shadow:
    inset 0 0 0 1px rgba(240, 180, 41, 0.2),
    0 3px 10px rgba(0, 0, 0, 0.28);
}

.slot.hot .mesh-led {
  background: #ff5252;
  box-shadow: 0 0 5px rgba(255, 82, 82, 0.95);
}

.slot.hot .rack-front {
  box-shadow:
    inset 0 0 0 1px rgba(255, 90, 90, 0.25),
    0 3px 12px rgba(180, 40, 40, 0.2);
}

.slot.active .rack-front {
  outline: 2px solid #60a5fa;
  outline-offset: 2px;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.08),
    0 0 14px rgba(96, 165, 250, 0.4);
}

.slot-code {
  position: absolute;
  left: 50%;
  bottom: -16px;
  transform: translateX(-50%);
  font-size: 9px;
  color: rgba(170, 205, 215, 0.78);
  white-space: nowrap;
  pointer-events: none;
}

.tip {
  position: absolute;
  right: 10px;
  top: 10px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  z-index: 3;
  pointer-events: none;
  max-width: min(240px, 42%);
}

.reticle {
  width: 18px;
  height: 18px;
  border: 1px solid var(--accent, #1ec8a5);
  border-radius: 50%;
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent, #1ec8a5) 18%, transparent);
  position: relative;
  flex-shrink: 0;
}

.reticle::before,
.reticle::after {
  content: '';
  position: absolute;
  background: var(--accent, #1ec8a5);
}

.reticle::before {
  width: 1px;
  height: 26px;
  left: 50%;
  top: -4px;
  transform: translateX(-50%);
}

.reticle::after {
  height: 1px;
  width: 26px;
  top: 50%;
  left: -4px;
  transform: translateY(-50%);
}

.tip-card {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 168px;
  max-width: 220px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid color-mix(in srgb, var(--accent, #1ec8a5) 55%, transparent);
  background: rgba(6, 20, 30, 0.94);
  font-size: 11px;
  color: rgba(190, 220, 225, 0.9);
  pointer-events: auto;
}

.tip-card strong {
  color: #9fe8d8;
  font-size: 13px;
}

.tip-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}

.tip-btn {
  height: 28px;
  border-radius: 6px;
  border: 1px solid rgba(64, 180, 190, 0.45);
  background: rgba(8, 28, 40, 0.95);
  color: #d7ece8;
  font-size: 12px;
  cursor: pointer;
}

.tip-btn.primary {
  border-color: rgba(30, 200, 165, 0.7);
  background: rgba(20, 90, 80, 0.55);
  color: #9fe8d8;
}

.tip-btn:hover {
  border-color: #1ec8a5;
}

.rack-dialog-mask {
  position: fixed;
  inset: 0;
  z-index: 40;
  background: rgba(2, 10, 16, 0.72);
  display: grid;
  place-items: center;
  padding: 24px;
  box-sizing: border-box;
}

.rack-dialog {
  width: min(520px, 100%);
  max-height: min(86vh, 920px);
  display: flex;
  flex-direction: column;
  border-radius: 12px;
  border: 1px solid rgba(30, 200, 165, 0.4);
  background: linear-gradient(180deg, #0b1c28, #07131c);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.45);
  overflow: hidden;
}

.rack-dialog-head,
.rack-dialog-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid rgba(64, 180, 190, 0.2);
}

.rack-dialog-foot {
  border-bottom: none;
  border-top: 1px solid rgba(64, 180, 190, 0.2);
  justify-content: flex-end;
}

.rack-dialog-head h4 {
  margin: 0;
  font-size: 15px;
  color: #9fe8d8;
}

.rack-dialog-head p {
  margin: 4px 0 0;
  font-size: 12px;
  color: rgba(170, 205, 215, 0.72);
}

.rack-dialog-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 12px 14px 16px;
}

.rack-dialog-body.loading,
.rack-dialog-body.error {
  display: grid;
  place-items: center;
  min-height: 220px;
  color: rgba(170, 205, 215, 0.8);
}

.rack-dialog-body.error {
  color: #e35d5b;
}

.rack-dialog-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin-bottom: 12px;
  font-size: 12px;
  color: rgba(190, 220, 225, 0.88);
}

.rack-dialog-cabinet {
  display: flex;
  justify-content: center;
  padding-bottom: 8px;
}

.gesture-hint {
  position: absolute;
  left: 12px;
  bottom: 10px;
  margin: 0;
  font-size: 11px;
  color: rgba(170, 205, 215, 0.55);
  pointer-events: none;
  z-index: 2;
}

.legend {
  display: flex;
  gap: 14px;
  justify-content: flex-end;
  font-size: 11px;
  color: rgba(170, 205, 215, 0.72);
}

.legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  display: inline-block;
}

.dot.ok { background: #1ec8a5; }
.dot.warm { background: #f0b429; }
.dot.hot { background: #e35d5b; }
.dot.empty {
  background: transparent;
  border: 1px dashed rgba(120, 160, 170, 0.7);
}

/* —— studio：管理端浅色仿真 —— */
.monitor.variant-studio {
  height: 100%;
  padding: 8px 10px 10px;
  background: transparent;
}

.variant-studio .panel-title {
  color: #2a4a6a;
}

.variant-studio .sub,
.variant-studio .room-select,
.variant-studio .scale-label,
.variant-studio .hint,
.variant-studio .legend {
  color: #5a7088;
}

.variant-studio .room-select select,
.variant-studio .tool-btn {
  border-color: #b8cce0;
  background: #fff;
  color: #2a3d52;
}

.variant-studio .tool-btn:hover {
  border-color: #3aa0ff;
  color: #1a6fd0;
}

.variant-studio .stage {
  border-color: rgba(150, 180, 210, 0.55);
  background:
    radial-gradient(ellipse at 50% 8%, rgba(255, 255, 255, 0.9), transparent 52%),
    linear-gradient(180deg, #eef5fc 0%, #d5e4f3 100%);
}

.variant-studio .iso-floor {
  background-image:
    linear-gradient(rgba(150, 170, 190, 0.28) 1px, transparent 1px),
    linear-gradient(90deg, rgba(150, 170, 190, 0.28) 1px, transparent 1px);
  background-size: 28px 28px;
  background-color: rgba(236, 242, 248, 0.55);
  border: 1px solid rgba(170, 190, 210, 0.4);
  border-radius: 4px;
  box-shadow:
    0 18px 40px rgba(60, 90, 130, 0.12),
    inset 0 0 0 1px rgba(255, 255, 255, 0.5);
}

.variant-studio .row-tag,
.variant-studio .slot-code {
  color: #6a8098;
}

.variant-studio .slot.empty .rack-front {
  background: rgba(255, 255, 255, 0.55);
  border: 1px dashed rgba(140, 170, 200, 0.55);
}

.variant-studio .aisle-vent {
  opacity: 1;
  background:
    radial-gradient(circle, rgba(55, 65, 75, 0.65) 1.1px, transparent 1.3px) 0 0 / 5px 5px,
    linear-gradient(180deg, #a8b0ba, #8a939e);
}

.variant-studio .tip-card {
  background: rgba(255, 255, 255, 0.95);
  border-color: rgba(160, 190, 220, 0.7);
  color: #2a3d52;
  box-shadow: 0 8px 24px rgba(40, 70, 110, 0.12);
}

.variant-studio .gesture-hint {
  color: rgba(90, 112, 136, 0.7);
}
</style>
