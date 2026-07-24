<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import {
  CORE_CARD_TYPE_LABELS,
  NODE_KIND_LABELS,
  PORT_TYPE_COLORS,
  PORT_TYPE_LABELS,
  SERVER_ORIENTATION_LABELS,
  SERVER_SLOT_KIND_LABELS,
  SWITCH_SUBTYPE_DEFAULTS,
  SWITCH_SUBTYPE_LABELS,
  UPLINK_POSITION_LABELS,
  formatNodeLocation,
  listNodePortOptions,
  newCoreLineCard,
  type CoreCardType,
  type CoreLineCard,
  type FramePort,
  type NetworkNode,
  type PortLayout,
  type PortType,
  type ServerFormFactor,
  type ServerPanelSide,
  type ServerSlotKind,
  type ServerSlotOrientation,
  type SwitchSubtype,
  type UplinkPosition,
} from '@/api/network'
import {
  EAR_WIDTH_PX,
  EDITOR_MM_SCALE,
  FRAME_HEADER_PX,
  LAYOUT_PAD_X,
  LAYOUT_PAD_Y,
  MAX_HEIGHT_U,
  MAX_SLOT_COUNT,
  addGroupToSlot,
  addServerSlot,
  addSlotWithGroup,
  applyHeightU,
  applySwitchLayoutConfig,
  defaultPortLayout,
  formatDeviceFrameLabel,
  frameDisplayScalePercent,
  groupVisualLayouts,
  layoutDisplayScale,
  moveSlotInFrame,
  normalizePortLayout,
  readSwitchLayoutConfig,
  removeSlot,
  reorderGroupInSlot,
  slotBandRects,
  moveServerPortInPanel,
  moveServerSlotInPanel,
  syncLegacyFromPortLayout,
  syncPortsFromSlotsDef,
} from '@/utils/networkPortLayout'
import { PANEL_EAR, layoutSwitchFrontPanel, normalizeGigabitUplinkCount, normalizeTenGigabitUplinkCount } from '@/utils/switchFrontPanel'
import {
  applyServerFormFactor,
  layoutServerRearPanel,
  normalizeServerFormFactor,
  normalizeServerSlotPortCount,
  resolveSlotSize,
  resizeServerSlotInPanel,
  SERVER_RESIZE_HANDLE,
  SERVER_SLOT_PORT_MAX,
  type ServerPanelView,
} from '@/utils/serverRearPanel'
import { layoutServerFrontPanel, type ServerFrontPanelView } from '@/utils/serverFrontPanel'
import { SERVER_CARD_PALETTE } from '@/utils/serverPanelCommon'

const props = defineProps<{
  node: NetworkNode
  peerNodes: NetworkNode[]
  /** 是否可配置接口（对端/标签） */
  editable?: boolean
  /** 是否可编辑布局结构（拖动卡槽、改数量等）；默认与 editable 相同 */
  layoutEditable?: boolean
}>()

const layoutCanEdit = computed(() =>
  props.layoutEditable ?? props.editable ?? false,
)
const portsCanEdit = computed(() => props.editable ?? false)

const layout = computed(() => {
  if (!props.node.port_layout) {
    props.node.port_layout = defaultPortLayout(props.node.kind)
    if (props.node.kind === 'switch') {
      applySwitchLayoutConfig(props.node.port_layout, {
        subtype: 'gigabit',
        mainPortCount: 48,
        uplinkPortCount: 4,
        uplinkPosition: 'right',
      })
    } else if (props.node.kind === 'server') {
      applyServerFormFactor(props.node.port_layout, 1)
      syncPortsFromSlotsDef(props.node.port_layout, false)
    } else {
      syncPortsFromSlotsDef(props.node.port_layout, false)
    }
  } else {
    normalizePortLayout(props.node.port_layout)
    if (props.node.kind === 'switch' && !props.node.port_layout.switch_subtype) {
      applySwitchLayoutConfig(props.node.port_layout, {
        subtype: 'gigabit',
        mainPortCount: props.node.port_layout.main_port_count ?? 48,
        uplinkPortCount: props.node.port_layout.uplink_port_count ?? 4,
        uplinkPosition: props.node.port_layout.uplink_position ?? 'right',
      })
    } else if (props.node.kind === 'server' && props.node.port_layout.server_form_factor == null) {
      applyServerFormFactor(props.node.port_layout, normalizeServerFormFactor(props.node.port_layout.height_u ?? 1))
      syncPortsFromSlotsDef(props.node.port_layout, true)
    } else if (!props.node.port_layout.ports.length) {
      syncPortsFromSlotsDef(props.node.port_layout, false)
    }
  }
  return props.node.port_layout as PortLayout
})

const displayScale = ref(frameDisplayScalePercent(layout.value))
/** 图形显示缩放（仅影响预览，不改布局坐标） */
const viewZoom = ref(props.node.kind === 'server' ? 55 : props.node.kind === 'switch' ? 80 : 100)
const VIEW_ZOOM_MIN = 30
const VIEW_ZOOM_MAX = 200
const VIEW_ZOOM_STEP = 10

const selectedPortId = ref<string | null>(null)
const selectedGroupId = ref<string | null>(null)
const peerVisible = ref(false)
const portEditVisible = ref(false)
const addSlotVisible = ref(false)
const addGroupVisible = ref(false)
const addGroupSlotIdx = ref(0)
const panelView = ref<ReturnType<typeof layoutSwitchFrontPanel> | null>(null)
const serverPanelView = ref<ServerPanelView | null>(null)
const serverFrontPanelView = ref<ServerFrontPanelView | null>(null)

const serverPanelSide = computed({
  get: () => (layout.value.server_panel_side ?? 'rear') as ServerPanelSide,
  set: (v: ServerPanelSide) => {
    layout.value.server_panel_side = v
    refreshServerPanel()
    syncLegacyFromPortLayout(props.node)
  },
})

const addForm = reactive({
  port_type: '1g' as PortType,
  count: 1,
  server_slot_kind: 'nic_10g' as ServerSlotKind,
})

const switchForm = reactive({
  subtype: 'gigabit' as SwitchSubtype,
  main_port_count: 48,
  uplink_port_count: 4,
  uplink_position: 'right' as UplinkPosition,
  line_cards: [newCoreLineCard()] as CoreLineCard[],
})

const serverForm = reactive({
  form_factor: 1 as ServerFormFactor,
  onboard_1g_count: 4,
})

const peerForm = reactive({
  peer_node_id: '' as string | null,
  peer_port: '' as string | null,
  peer_label: '',
})

const portForm = reactive({
  label: '',
})

const isSwitch = computed(() => props.node.kind === 'switch')
const isServer = computed(() => props.node.kind === 'server')
const isCoreSwitch = computed(() => isSwitch.value && switchForm.subtype === 'core')
const isGigabitSwitch = computed(() => isSwitch.value && switchForm.subtype === 'gigabit')
const isTenGigabitSwitch = computed(() => isSwitch.value && switchForm.subtype === 'ten_gigabit')

const slotBands = computed(() => (isSwitch.value || isServer.value ? [] : slotBandRects(layout.value)))
const groupLayouts = computed(() => (isSwitch.value || isServer.value ? [] : groupVisualLayouts(layout.value)))
const svgOffset = computed(() =>
  isSwitch.value || isServer.value ? PANEL_EAR + 6 : EAR_WIDTH_PX + 6,
)
const svgRef = ref<SVGSVGElement | null>(null)

const svgNaturalWidth = computed(() => layout.value.frame_width + svgOffset.value * 2)
const svgNaturalHeight = computed(() => layout.value.frame_height + 28)
const svgDisplayWidth = computed(() => Math.round(svgNaturalWidth.value * (viewZoom.value / 100)))
const svgDisplayHeight = computed(() => Math.round(svgNaturalHeight.value * (viewZoom.value / 100)))
const svgViewBox = computed(() => `0 0 ${svgNaturalWidth.value} ${svgNaturalHeight.value}`)

function defaultViewZoomForKind() {
  if (isServer.value) return 55
  if (isSwitch.value) return 80
  return 100
}

function onViewZoomChange(val: number | number[] | undefined) {
  const n = Array.isArray(val) ? val[0] : val
  if (n == null || Number.isNaN(Number(n))) return
  viewZoom.value = Math.max(VIEW_ZOOM_MIN, Math.min(VIEW_ZOOM_MAX, Math.round(Number(n))))
}

function bumpViewZoom(delta: number) {
  onViewZoomChange(viewZoom.value + delta)
}

function resetViewZoom() {
  viewZoom.value = defaultViewZoomForKind()
}

function refreshSwitchPanel() {
  if (!isSwitch.value || !layout.value.switch_subtype) {
    panelView.value = null
    return
  }
  panelView.value = layoutSwitchFrontPanel(layout.value)
}

function refreshServerPanel() {
  if (!isServer.value) {
    serverPanelView.value = null
    serverFrontPanelView.value = null
    return
  }
  if (layout.value.server_form_factor == null) {
    applyServerFormFactor(layout.value, 1)
  }
  if (layout.value.server_onboard_1g_count == null) {
    layout.value.server_onboard_1g_count = 4
  }
  if (serverPanelSide.value === 'front') {
    serverFrontPanelView.value = layoutServerFrontPanel(layout.value)
    serverPanelView.value = null
  } else {
    serverPanelView.value = layoutServerRearPanel(layout.value)
    serverFrontPanelView.value = null
  }
}

function syncServerFormFromLayout() {
  if (!isServer.value) return
  serverForm.form_factor = normalizeServerFormFactor(layout.value.server_form_factor ?? layout.value.height_u ?? 1)
  serverForm.onboard_1g_count = layout.value.server_onboard_1g_count ?? 4
}

const selectedPort = computed(() =>
  layout.value.ports.find((p) => p.id === selectedPortId.value) || null,
)

const peerPortOptions = computed(() => {
  if (!peerForm.peer_node_id) return []
  const peer = props.peerNodes.find((n) => n.id === peerForm.peer_node_id)
  return peer ? listNodePortOptions(peer) : []
})

const selectedPeerNode = computed(() =>
  props.peerNodes.find((n) => n.id === peerForm.peer_node_id) || null,
)

function portCaptionY(port: FramePort) {
  const siblings = layout.value.ports.filter((p) => p.group_id === port.group_id)
  if (siblings.length <= 1) return port.y - 2
  const minY = Math.min(...siblings.map((p) => p.y))
  return Math.abs(port.y - minY) < 1.5 ? port.y - 2 : port.y + port.h + 8
}

function slotGroupedRows(slot: { groups?: { id: string; port_type: PortType; count: number }[] }) {
  const map = new Map<PortType, { port_type: PortType; count: number; groupIds: string[] }>()
  ;(slot.groups || []).forEach((g) => {
    const row = map.get(g.port_type)
    if (row) {
      row.count += g.count
      row.groupIds.push(g.id)
    } else {
      map.set(g.port_type, { port_type: g.port_type, count: g.count, groupIds: [g.id] })
    }
  })
  return [...map.values()]
}

function onGroupedCountChange(slotIdx: number, portType: PortType, count: number | undefined) {
  if (count == null) return
  const slot = layout.value.slots_def?.[slotIdx]
  if (!slot?.groups?.length) return
  const same = slot.groups.filter((g) => g.port_type === portType)
  if (!same.length) return
  const n = Math.max(1, count)
  if (same.length === 1) {
    same[0].count = n
  } else if (same.length === 2) {
    const left = Math.max(1, Math.floor(n / 2))
    const right = Math.max(0, n - left)
    same[0].count = left
    if (right <= 0) {
      slot.groups = slot.groups.filter((g) => g.id !== same[1].id)
    } else {
      same[1].count = right
    }
  } else {
    same[0].count = n
    const keepId = same[0].id
    slot.groups = slot.groups.filter((g) => g.port_type !== portType || g.id === keepId)
  }
  if (!slot.groups.length) {
    slot.groups.push({
      id: crypto.randomUUID().slice(0, 8),
      port_type: portType,
      count: n,
      role: 'main',
      layout_x: null,
      layout_y: null,
    })
  }
  applyLayout()
}

function onRemoveGroupedType(slotIdx: number, portType: PortType) {
  const slot = layout.value.slots_def?.[slotIdx]
  if (!slot) return
  const remaining = slot.groups.filter((g) => g.port_type !== portType)
  if (!remaining.length) return
  slot.groups = remaining
  applyLayout()
}

const draggingServerPort = ref<{
  portId: string
  offsetX: number
  offsetY: number
} | null>(null)
const resizingServerSlot = ref<{
  slotIndex: number
  startX: number
  startY: number
  originW: number
  originH: number
} | null>(null)
const selectedServerSlotIdx = ref<number | null>(null)
const draggingGroup = ref<{
  slotIndex: number
  groupId: string
  offsetY: number
} | null>(null)
const draggingSlot = ref<{
  slotIndex: number
  offsetX: number
  offsetY: number
} | null>(null)
const pendingDragCenterY = ref<number | null>(null)

function slotWidthMm(band: (typeof slotBands.value)[0]) {
  const ds = layoutDisplayScale(layout.value)
  return Math.round(band.contentW / ds / EDITOR_MM_SCALE)
}

function portColors(port: FramePort) {
  return PORT_TYPE_COLORS[port.port_type || '1g']
}

function groupColors(portType: PortType) {
  return PORT_TYPE_COLORS[portType]
}

function onHeightUChange(val: number | undefined) {
  if (val == null || !layoutCanEdit.value) return
  applyHeightU(layout.value, val)
  displayScale.value = frameDisplayScalePercent(layout.value)
}

function applyLayout() {
  syncPortsFromSlotsDef(layout.value)
  displayScale.value = frameDisplayScalePercent(layout.value)
  refreshSwitchPanel()
  refreshServerPanel()
}

function syncSwitchFormFromLayout() {
  if (!isSwitch.value) return
  const config = readSwitchLayoutConfig(layout.value)
  switchForm.subtype = config.subtype
  switchForm.main_port_count = config.mainPortCount
  switchForm.uplink_port_count = config.uplinkPortCount
  switchForm.uplink_position = config.uplinkPosition
  switchForm.line_cards = config.lineCards?.length
    ? config.lineCards.map((c) => ({ ...c }))
    : [newCoreLineCard()]
}

function onSwitchSubtypeChange(subtype: SwitchSubtype) {
  const defaults = SWITCH_SUBTYPE_DEFAULTS[subtype]
  switchForm.main_port_count = defaults.mainPortCount
  switchForm.uplink_port_count = defaults.uplinkPortCount
  if (subtype === 'core' && !switchForm.line_cards.length) {
    switchForm.line_cards = [newCoreLineCard()]
  }
}

function onSubtypeSelect(subtype: SwitchSubtype) {
  onSwitchSubtypeChange(subtype)
  onSwitchFormChange()
}

function addEditorLineCard() {
  if (switchForm.line_cards.length >= 16) return
  switchForm.line_cards.push(newCoreLineCard())
}

function removeEditorLineCard(idx: number) {
  if (switchForm.line_cards.length <= 1) return
  switchForm.line_cards.splice(idx, 1)
}

function applySwitchTemplate() {
  applySwitchLayoutConfig(layout.value, {
    subtype: switchForm.subtype,
    mainPortCount: switchForm.main_port_count,
    uplinkPortCount: switchForm.uplink_port_count,
    uplinkPosition: switchForm.uplink_position,
    lineCards: switchForm.subtype === 'core' ? switchForm.line_cards : [],
  })
  syncLegacyFromPortLayout(props.node)
  displayScale.value = frameDisplayScalePercent(layout.value)
  refreshSwitchPanel()
}

function onServerFormFactorChange(val: ServerFormFactor | string | number) {
  const next = normalizeServerFormFactor(val)
  serverForm.form_factor = next
  applyServerFormFactor(layout.value, next)
  syncPortsFromSlotsDef(layout.value, true)
  syncLegacyFromPortLayout(props.node)
  refreshServerPanel()
}

function isPortlessServerSlot(kind: ServerSlotKind | null | undefined) {
  return kind === 'raid' || kind === 'blank'
}

function onServerSlotKindChange(slotIdx: number, kind: ServerSlotKind) {
  const slot = layout.value.slots_def?.[slotIdx]
  if (!slot) return
  slot.server_slot_kind = kind
  if (isPortlessServerSlot(kind)) {
    slot.groups = []
  } else {
    const portType = kind === 'nic_1g' ? '1g' : kind === 'nic_10g' ? '10g' : 'other'
    const count = slot.groups?.[0]?.count || 2
    slot.groups = [{
      id: slot.groups?.[0]?.id || crypto.randomUUID().slice(0, 8),
      port_type: portType,
      count,
      layout_x: null,
      layout_y: null,
    }]
  }
  applyLayout()
}

function onServerSlotPortCountChange(slotIdx: number, count: number | undefined) {
  if (count == null) return
  const slot = layout.value.slots_def?.[slotIdx]
  if (!slot || isPortlessServerSlot(slot.server_slot_kind)) return
  const n = normalizeServerSlotPortCount(count)
  if (!slot.groups.length) {
    const portType = slot.server_slot_kind === 'nic_1g' ? '1g' : slot.server_slot_kind === 'hba' ? 'other' : '10g'
    slot.groups = [{
      id: crypto.randomUUID().slice(0, 8),
      port_type: portType as PortType,
      count: n,
      layout_x: null,
      layout_y: null,
    }]
  } else {
    slot.groups[0].count = n
    ;(layout.value.ports || [])
      .filter((p) => p.slot_index === slotIdx + 1)
      .forEach((p) => { p.layout_locked = false })
  }
  applyLayout()
}

function onServerSlotOrientationChange(slotIdx: number, orientation: ServerSlotOrientation) {
  const slot = layout.value.slots_def?.[slotIdx]
  if (!slot) return
  // 1U 仅允许横向；2U/4U 可自由选择横/竖放
  const nextOri = serverForm.form_factor === 1 ? 'horizontal' : orientation
  const prevOri = slot.orientation || (serverForm.form_factor === 1 ? 'horizontal' : 'vertical')
  slot.orientation = nextOri
  const size = resolveSlotSize(
    { ...slot, orientation: nextOri, layout_w: null, layout_h: null },
    serverForm.form_factor,
  )
  slot.layout_w = size.w
  slot.layout_h = size.h
  // 方向变化时重新落位，避免竖卡坐标套用到横卡导致越界/重叠
  if (prevOri !== nextOri) {
    slot.layout_x = null
    slot.layout_y = null
  }
  ;(layout.value.ports || [])
    .filter((p) => p.slot_index === slotIdx + 1)
    .forEach((p) => { p.layout_locked = false })
  applyLayout()
}

function onServerSlotSizeChange(slotIdx: number, dim: 'w' | 'h', value: number | undefined) {
  if (value == null) return
  const slot = layout.value.slots_def?.[slotIdx]
  if (!slot) return
  const cur = resolveSlotSize(slot, serverForm.form_factor)
  resizeServerSlotInPanel(
    layout.value,
    slotIdx,
    dim === 'w' ? value : cur.w,
    dim === 'h' ? value : cur.h,
  )
  refreshServerPanel()
  syncLegacyFromPortLayout(props.node)
}

function onServerOnboard1gChange(count: number | undefined) {
  if (count == null) return
  layout.value.server_onboard_1g_count = Math.max(0, Math.min(8, count))
  serverForm.onboard_1g_count = layout.value.server_onboard_1g_count
  ;(layout.value.ports || [])
    .filter((p) => p.slot_index === 0)
    .forEach((p) => { p.layout_locked = false })
  applyLayout()
}

function onSwitchFormChange() {
  if (!layoutCanEdit.value || !isSwitch.value) return
  applySwitchTemplate()
}

function onGigabitUplinkChange(val: number | undefined) {
  if (val == null) return
  switchForm.uplink_port_count = normalizeGigabitUplinkCount(val)
  onSwitchFormChange()
}

function onTenGigabitUplinkChange(val: number | undefined) {
  if (val == null) return
  switchForm.uplink_port_count = normalizeTenGigabitUplinkCount(val)
  onSwitchFormChange()
}

function openAddSlot() {
  if (isServer.value) {
    addForm.server_slot_kind = 'nic_10g'
    addForm.count = 2
  } else {
    addForm.port_type = '1g'
    addForm.count = 2
  }
  addSlotVisible.value = true
}

function confirmAddSlot() {
  if (isServer.value) {
    addServerSlot(layout.value, addForm.server_slot_kind, addForm.count)
  } else {
    if ((layout.value.slots_def?.length ?? 0) >= MAX_SLOT_COUNT) return
    addSlotWithGroup(layout.value, addForm.port_type, addForm.count)
  }
  syncPortsFromSlotsDef(layout.value)
  displayScale.value = frameDisplayScalePercent(layout.value)
  refreshServerPanel()
  addSlotVisible.value = false
}

function openAddGroup(slotIdx: number) {
  addGroupSlotIdx.value = slotIdx
  addForm.port_type = '10g'
  addForm.count = 1
  addGroupVisible.value = true
}

function confirmAddGroup() {
  addGroupToSlot(layout.value, addGroupSlotIdx.value, addForm.port_type, addForm.count)
  syncPortsFromSlotsDef(layout.value)
  displayScale.value = frameDisplayScalePercent(layout.value)
  addGroupVisible.value = false
}

function onRemoveSlot(slotIdx: number) {
  removeSlot(layout.value, slotIdx)
  syncPortsFromSlotsDef(layout.value)
  displayScale.value = frameDisplayScalePercent(layout.value)
}

function openPeerDialog(port: FramePort) {
  if (!portsCanEdit.value) return
  selectedPortId.value = port.id
  selectedGroupId.value = port.group_id
  peerForm.peer_node_id = port.peer_node_id
  peerForm.peer_port = port.peer_port
  peerForm.peer_label = port.peer_label || ''
  peerVisible.value = true
}

function openPortEdit(port: FramePort) {
  if (!portsCanEdit.value) return
  selectedPortId.value = port.id
  portForm.label = port.label
  portEditVisible.value = true
}

function onPortClick(port: FramePort) {
  selectedPortId.value = port.id
  selectedGroupId.value = port.group_id
}

function onGroupClick(groupId: string) {
  selectedGroupId.value = groupId
  selectedPortId.value = null
}

function confirmPeer() {
  if (!selectedPort.value) return
  selectedPort.value.peer_node_id = peerForm.peer_node_id || null
  selectedPort.value.peer_port = peerForm.peer_port || null
  selectedPort.value.peer_label = peerForm.peer_label.trim() || null
  peerVisible.value = false
}

function confirmPortEdit() {
  if (!selectedPort.value) return
  selectedPort.value.label = portForm.label.trim() || selectedPort.value.id
  portEditVisible.value = false
}

function clearPeer() {
  if (!selectedPort.value) return
  selectedPort.value.peer_node_id = null
  selectedPort.value.peer_port = null
  selectedPort.value.peer_label = null
  peerForm.peer_node_id = null
  peerForm.peer_port = null
  peerForm.peer_label = ''
}

function portHitPad(port: FramePort) {
  const pad = Math.max(5, Math.min(8, Math.round(Math.min(port.w, port.h) * 0.35)))
  return {
    x: port.x - pad,
    y: port.y - pad,
    w: port.w + pad * 2,
    h: port.h + pad * 2 + 10,
  }
}

function portJackPath(port: FramePort): string {
  const { x, y, w, h } = port
  if (port.port_type === '40_100g') {
    const r = Math.min(2, w * 0.08)
    return [
      `M ${x + r} ${y}`,
      `L ${x + w - r} ${y}`,
      `Q ${x + w} ${y} ${x + w} ${y + r}`,
      `L ${x + w} ${y + h - r}`,
      `Q ${x + w} ${y + h} ${x + w - r} ${y + h}`,
      `L ${x + r} ${y + h}`,
      `Q ${x} ${y + h} ${x} ${y + h - r}`,
      `L ${x} ${y + r}`,
      `Q ${x} ${y} ${x + r} ${y}`,
      'Z',
    ].join(' ')
  }
  if (port.port_type === '10g') {
    const inset = Math.max(1.5, w * 0.12)
    const r = Math.min(1.5, w * 0.08)
    return [
      `M ${x + r} ${y}`,
      `L ${x + w - r} ${y}`,
      `Q ${x + w} ${y} ${x + w} ${y + r}`,
      `L ${x + w} ${y + h - r}`,
      `Q ${x + w} ${y + h} ${x + w - r} ${y + h}`,
      `L ${x + r} ${y + h}`,
      `Q ${x} ${y + h} ${x} ${y + h - r}`,
      `L ${x} ${y + r}`,
      `Q ${x} ${y} ${x + r} ${y}`,
      'Z',
      `M ${x + inset} ${y + inset}`,
      `L ${x + w - inset} ${y + inset}`,
      `L ${x + w - inset} ${y + h - inset}`,
      `L ${x + inset} ${y + h - inset}`,
      'Z',
    ].join(' ')
  }
  const tabW = Math.min(w * 0.55, w - 2)
  const tabH = Math.max(2, h * 0.22)
  const tabX = x + (w - tabW) / 2
  const r = Math.min(2, w * 0.12)
  return [
    `M ${x + r} ${y}`,
    `L ${tabX} ${y}`,
    `L ${tabX} ${y - tabH}`,
    `L ${tabX + tabW} ${y - tabH}`,
    `L ${tabX + tabW} ${y}`,
    `L ${x + w - r} ${y}`,
    `Q ${x + w} ${y} ${x + w} ${y + r}`,
    `L ${x + w} ${y + h - r}`,
    `Q ${x + w} ${y + h} ${x + w - r} ${y + h}`,
    `L ${x + r} ${y + h}`,
    `Q ${x} ${y + h} ${x} ${y + h - r}`,
    `L ${x} ${y + r}`,
    `Q ${x} ${y} ${x + r} ${y}`,
    'Z',
  ].join(' ')
}

function svgPoint(event: MouseEvent) {
  const svg = svgRef.value
  if (!svg) return null
  const pt = svg.createSVGPoint()
  pt.x = event.clientX
  pt.y = event.clientY
  return pt.matrixTransform(svg.getScreenCTM()?.inverse())
}

function onSlotMouseDown(event: MouseEvent, band: (typeof slotBands.value)[0]) {
  if (!layoutCanEdit.value || isSwitch.value) return
  event.stopPropagation()
  selectedGroupId.value = null
  selectedPortId.value = null
  const cursor = svgPoint(event)
  if (!cursor) return
  const frameX = cursor.x - svgOffset.value
  const frameY = cursor.y - 14
  draggingSlot.value = {
    slotIndex: band.slotIndex - 1,
    offsetX: frameX - band.x,
    offsetY: frameY - band.y,
  }
}

function onServerSlotMouseDown(event: MouseEvent, slot: NonNullable<typeof serverPanelView.value>['slots'][0]) {
  if (!layoutCanEdit.value || !isServer.value || serverPanelSide.value !== 'rear') return
  event.stopPropagation()
  selectedGroupId.value = null
  selectedPortId.value = null
  selectedServerSlotIdx.value = slot.slotIndex - 1
  const cursor = svgPoint(event)
  if (!cursor) return
  const frameX = cursor.x - svgOffset.value
  const frameY = cursor.y - 14
  draggingSlot.value = {
    slotIndex: slot.slotIndex - 1,
    offsetX: frameX - slot.x,
    offsetY: frameY - slot.y,
  }
}

function onServerSlotResizeMouseDown(
  event: MouseEvent,
  slot: NonNullable<typeof serverPanelView.value>['slots'][0],
) {
  if (!layoutCanEdit.value || !isServer.value || serverPanelSide.value !== 'rear') return
  event.stopPropagation()
  selectedServerSlotIdx.value = slot.slotIndex - 1
  const cursor = svgPoint(event)
  if (!cursor) return
  resizingServerSlot.value = {
    slotIndex: slot.slotIndex - 1,
    startX: cursor.x - svgOffset.value,
    startY: cursor.y - 14,
    originW: slot.w,
    originH: slot.h,
  }
}

function onServerPortMouseDown(event: MouseEvent, port: FramePort) {
  event.stopPropagation()
  selectedPortId.value = port.id
  selectedGroupId.value = port.group_id
  if (!layoutCanEdit.value || !isServer.value || serverPanelSide.value !== 'rear') return
  const cursor = svgPoint(event)
  if (!cursor) return
  const frameX = cursor.x - svgOffset.value
  const frameY = cursor.y - 14
  draggingServerPort.value = {
    portId: port.id,
    offsetX: frameX - port.x,
    offsetY: frameY - port.y,
  }
}

function serverCardPalette(kind: ServerSlotKind) {
  return SERVER_CARD_PALETTE[kind] || SERVER_CARD_PALETTE.blank
}

function serverCardBracketRects(slot: NonNullable<typeof serverPanelView.value>['slots'][0]) {
  if (slot.orientation === 'vertical') {
    return {
      x: slot.x,
      y: slot.y,
      w: 7,
      h: slot.h,
      rivets: [
        { cx: slot.x + 3.5, cy: slot.y + 8 },
        { cx: slot.x + 3.5, cy: slot.y + slot.h - 8 },
      ],
    }
  }
  return {
    x: slot.x,
    y: slot.y,
    w: slot.w,
    h: 6,
    rivets: [
      { cx: slot.x + 8, cy: slot.y + 3 },
      { cx: slot.x + slot.w - 8, cy: slot.y + 3 },
    ],
  }
}

function serverCardFaceRect(slot: NonNullable<typeof serverPanelView.value>['slots'][0]) {
  if (slot.orientation === 'vertical') {
    return { x: slot.x + 7, y: slot.y, w: Math.max(8, slot.w - 7), h: slot.h }
  }
  return { x: slot.x, y: slot.y + 6, w: slot.w, h: Math.max(8, slot.h - 6) }
}

function serverBlankFillerMarks(slot: NonNullable<typeof serverPanelView.value>['slots'][0]) {
  const face = serverCardFaceRect(slot)
  const marks: Array<{ x1: number; y1: number; x2: number; y2: number }> = []
  if (slot.orientation === 'vertical') {
    for (let i = 1; i <= 4; i += 1) {
      const y = face.y + (face.h * i) / 5
      marks.push({ x1: face.x + 4, y1: y, x2: face.x + face.w - 4, y2: y })
    }
  } else {
    for (let i = 1; i <= 3; i += 1) {
      const x = face.x + (face.w * i) / 4
      marks.push({ x1: x, y1: face.y + 4, x2: x, y2: face.y + face.h - 4 })
    }
  }
  return marks
}

function onGroupMouseDown(event: MouseEvent, group: (typeof groupLayouts.value)[0]) {
  if (!layoutCanEdit.value || draggingSlot.value || isSwitch.value) return
  event.stopPropagation()
  selectedGroupId.value = group.groupId
  selectedPortId.value = null
  const cursor = svgPoint(event)
  if (!cursor) return
  const frameY = cursor.y - 14
  draggingGroup.value = {
    slotIndex: group.slotIndex - 1,
    groupId: group.groupId,
    offsetY: frameY - (group.y + group.h / 2),
  }
}

function onMouseMove(event: MouseEvent) {
  if (isSwitch.value) return
  const cursor = svgPoint(event)
  if (!cursor) return
  const frameX = cursor.x - svgOffset.value
  const frameY = cursor.y - 14

  if (resizingServerSlot.value) {
    const dx = frameX - resizingServerSlot.value.startX
    const dy = frameY - resizingServerSlot.value.startY
    resizeServerSlotInPanel(
      layout.value,
      resizingServerSlot.value.slotIndex,
      resizingServerSlot.value.originW + dx,
      resizingServerSlot.value.originH + dy,
    )
    refreshServerPanel()
    return
  }

  if (draggingServerPort.value) {
    moveServerPortInPanel(
      layout.value,
      draggingServerPort.value.portId,
      frameX - draggingServerPort.value.offsetX,
      frameY - draggingServerPort.value.offsetY,
    )
    return
  }

  if (draggingSlot.value && isServer.value) {
    moveServerSlotInPanel(
      layout.value,
      draggingSlot.value.slotIndex,
      frameX - draggingSlot.value.offsetX,
      frameY - draggingSlot.value.offsetY,
    )
    refreshServerPanel()
    return
  }

  if (draggingSlot.value) {
    const ds = layoutDisplayScale(layout.value)
    const contentOriginX = LAYOUT_PAD_X * ds
    const contentOriginY = FRAME_HEADER_PX + LAYOUT_PAD_Y * ds
    const relX = frameX - draggingSlot.value.offsetX - contentOriginX
    const relY = frameY - draggingSlot.value.offsetY - contentOriginY
    moveSlotInFrame(layout.value, draggingSlot.value.slotIndex, relX, relY)
    return
  }

  if (!draggingGroup.value) return
  pendingDragCenterY.value = frameY - draggingGroup.value.offsetY
}

function onMouseUp() {
  if (resizingServerSlot.value || draggingServerPort.value || (draggingSlot.value && isServer.value)) {
    syncLegacyFromPortLayout(props.node)
  }
  resizingServerSlot.value = null
  draggingServerPort.value = null
  if (draggingGroup.value && pendingDragCenterY.value != null) {
    reorderGroupInSlot(
      layout.value,
      draggingGroup.value.slotIndex,
      draggingGroup.value.groupId,
      pendingDragCenterY.value,
    )
  }
  draggingGroup.value = null
  draggingSlot.value = null
  pendingDragCenterY.value = null
}

watch(
  () => props.node.id,
  () => {
    displayScale.value = frameDisplayScalePercent(layout.value)
    syncSwitchFormFromLayout()
    syncServerFormFromLayout()
    refreshSwitchPanel()
    refreshServerPanel()
    viewZoom.value = defaultViewZoomForKind()
  },
)

watch(
  () => props.node.kind,
  () => {
    viewZoom.value = defaultViewZoomForKind()
  },
)

watch(
  () => layout.value.switch_subtype,
  () => {
    syncSwitchFormFromLayout()
    refreshSwitchPanel()
  },
)

watch(
  () => layout.value.server_form_factor,
  () => {
    syncServerFormFromLayout()
    refreshServerPanel()
  },
)

watch(
  () => peerForm.peer_node_id,
  () => {
    if (peerForm.peer_port && !peerPortOptions.value.some((p) => p.id === peerForm.peer_port)) {
      peerForm.peer_port = null
    }
  },
)

syncSwitchFormFromLayout()
syncServerFormFromLayout()
refreshSwitchPanel()
refreshServerPanel()
</script>

<template>
  <div class="frame-editor" @mousemove="onMouseMove" @mouseup="onMouseUp" @mouseleave="onMouseUp">
    <div v-if="layoutCanEdit" class="config-panel">
      <div v-if="isSwitch" class="switch-config">
        <div class="config-row">
          <label>设备类型</label>
          <el-select
            v-model="switchForm.subtype"
            size="small"
            style="width: 140px"
            @change="onSubtypeSelect"
          >
            <el-option v-for="(label, key) in SWITCH_SUBTYPE_LABELS" :key="key" :label="label" :value="key" />
          </el-select>

          <template v-if="isGigabitSwitch">
            <label>电口数量</label>
            <el-input-number
              v-model="switchForm.main_port_count"
              :min="1"
              :max="128"
              size="small"
              @change="onSwitchFormChange"
            />
            <label>上联光口</label>
            <el-input-number
              v-model="switchForm.uplink_port_count"
              :min="0"
              :max="8"
              :step="1"
              size="small"
              @change="onGigabitUplinkChange"
            />
            <span class="field-hint">≤8，&gt;4 须为偶数</span>
            <label>上联位置</label>
            <el-radio-group v-model="switchForm.uplink_position" size="small" @change="onSwitchFormChange">
              <el-radio-button v-for="(label, key) in UPLINK_POSITION_LABELS" :key="key" :value="key">
                {{ label }}
              </el-radio-button>
            </el-radio-group>
          </template>

          <template v-else-if="isTenGigabitSwitch">
            <label>光口数量</label>
            <el-input-number
              v-model="switchForm.main_port_count"
              :min="1"
              :max="128"
              size="small"
              @change="onSwitchFormChange"
            />
            <label>40/100G</label>
            <el-input-number
              v-model="switchForm.uplink_port_count"
              :min="0"
              :max="8"
              :step="2"
              size="small"
              @change="onTenGigabitUplinkChange"
            />
            <span class="field-hint">≤8，须为偶数，两排向后扩展</span>
            <label>上联位置</label>
            <el-radio-group v-model="switchForm.uplink_position" size="small" @change="onSwitchFormChange">
              <el-radio-button v-for="(label, key) in UPLINK_POSITION_LABELS" :key="key" :value="key">
                {{ label }}
              </el-radio-button>
            </el-radio-group>
          </template>
        </div>

        <div v-if="isCoreSwitch" class="card-editor">
          <div v-for="(card, idx) in switchForm.line_cards" :key="card.id" class="card-editor-row">
            <span>板卡 {{ idx + 1 }}</span>
            <el-select v-model="card.card_type" size="small" style="width: 120px" @change="onSwitchFormChange">
              <el-option
                v-for="(label, key) in CORE_CARD_TYPE_LABELS"
                :key="key"
                :label="label"
                :value="key as CoreCardType"
              />
            </el-select>
            <label>接口数</label>
            <el-input-number
              v-model="card.port_count"
              :min="1"
              :max="128"
              size="small"
              @change="onSwitchFormChange"
            />
            <el-button
              type="danger"
              link
              size="small"
              :disabled="switchForm.line_cards.length <= 1"
              @click="removeEditorLineCard(idx); onSwitchFormChange()"
            >
              删除
            </el-button>
          </div>
          <div class="card-editor-actions">
            <el-button
              type="primary"
              link
              size="small"
              :disabled="switchForm.line_cards.length >= 16"
              @click="addEditorLineCard(); onSwitchFormChange()"
            >
              + 添加板卡
            </el-button>
            <span class="card-editor-hint">核心机框按板卡纵向排列，无独立上联口</span>
          </div>
        </div>
      </div>

      <template v-else-if="isServer">
        <div class="config-row">
          <label>面板</label>
          <el-radio-group v-model="serverPanelSide" size="small">
            <el-radio-button value="front">前面板</el-radio-button>
            <el-radio-button value="rear">后面板</el-radio-button>
          </el-radio-group>
          <label>服务器规格</label>
          <el-radio-group
            v-model="serverForm.form_factor"
            size="small"
            @change="onServerFormFactorChange"
          >
            <el-radio-button :value="1">1U</el-radio-button>
            <el-radio-button :value="2">2U</el-radio-button>
            <el-radio-button :value="4">4U</el-radio-button>
          </el-radio-group>
          <template v-if="serverPanelSide === 'rear'">
            <label>板载千兆</label>
            <el-input-number
              :model-value="serverForm.onboard_1g_count"
              :min="0"
              :max="8"
              size="small"
              @change="onServerOnboard1gChange"
            />
            <el-button
              type="primary"
              size="small"
              @click="openAddSlot"
            >
              + 添加扩展卡
            </el-button>
          </template>
        </div>

        <div v-if="serverPanelSide === 'rear'" class="slot-config-scroll">
          <div class="slot-config">
            <div v-for="(slot, idx) in layout.slots_def" :key="idx" class="slot-block server-slot-block">
              <div class="slot-header">
                <span class="slot-label">扩展卡 {{ idx + 1 }}</span>
                <el-button
                  v-if="(layout.slots_def?.length ?? 0) > 1"
                  size="small"
                  type="danger"
                  link
                  @click="onRemoveSlot(idx); refreshServerPanel()"
                >
                  删除
                </el-button>
              </div>
              <el-select
                :model-value="slot.server_slot_kind || 'nic_10g'"
                size="small"
                style="width: 100%"
                @change="(v: string) => onServerSlotKindChange(idx, v as ServerSlotKind)"
              >
                <el-option
                  v-for="(label, key) in SERVER_SLOT_KIND_LABELS"
                  :key="key"
                  :label="label"
                  :value="key"
                />
              </el-select>
              <div class="group-row">
                <span>放置</span>
                <el-select
                  :model-value="serverForm.form_factor === 1 ? 'horizontal' : (slot.orientation || 'vertical')"
                  size="small"
                  style="flex: 1"
                  :disabled="serverForm.form_factor === 1"
                  @change="(v: string) => onServerSlotOrientationChange(idx, v as ServerSlotOrientation)"
                >
                  <el-option
                    v-for="(label, key) in SERVER_ORIENTATION_LABELS"
                    :key="key"
                    :label="label"
                    :value="key"
                  />
                </el-select>
                <span v-if="serverForm.form_factor === 1" class="field-hint">1U 固定横向</span>
                <span v-else class="field-hint">横放贴底 / 竖放靠右</span>
              </div>
              <div class="group-row">
                <span>宽</span>
                <el-input-number
                  :model-value="Math.round(slot.layout_w || resolveSlotSize(slot, serverForm.form_factor).w)"
                  :min="28"
                  :max="320"
                  :step="2"
                  size="small"
                  @change="(val: number | undefined) => onServerSlotSizeChange(idx, 'w', val)"
                />
                <span>高</span>
                <el-input-number
                  :model-value="Math.round(slot.layout_h || resolveSlotSize(slot, serverForm.form_factor).h)"
                  :min="28"
                  :max="320"
                  :step="2"
                  size="small"
                  @change="(val: number | undefined) => onServerSlotSizeChange(idx, 'h', val)"
                />
              </div>
              <div v-if="!isPortlessServerSlot(slot.server_slot_kind)" class="group-row">
                <span>接口数</span>
                <el-input-number
                  :model-value="slot.groups?.[0]?.count || 1"
                  :min="1"
                  :max="SERVER_SLOT_PORT_MAX"
                  size="small"
                  @change="(val: number | undefined) => onServerSlotPortCountChange(idx, val)"
                />
              </div>
              <div v-if="!isPortlessServerSlot(slot.server_slot_kind) && (slot.groups?.[0]?.count || 0) > 5" class="raid-hint">
                超过 5 个接口须为偶数（6/8/10），两列或两行均匀排列
              </div>
              <div v-else class="raid-hint">
                {{ slot.server_slot_kind === 'blank' ? '预留挡板，无接口' : 'RAID 卡无对外网络接口' }}
              </div>
              <p v-if="layoutCanEdit" class="drag-hint">拖动卡体移动；拖右下角手柄缩放</p>
            </div>
          </div>
        </div>
      </template>

      <template v-else>
        <div class="config-row">
          <label>设备高度 (U)</label>
          <el-input-number
            :model-value="layout.height_u ?? 1"
            :min="1"
            :max="MAX_HEIGHT_U"
            size="small"
            @change="onHeightUChange"
          />
          <span class="frame-size">{{ formatDeviceFrameLabel(layout) }}</span>
          <el-button type="primary" size="small" :disabled="(layout.slots_def?.length ?? 0) >= MAX_SLOT_COUNT" @click="openAddSlot">
            + 添加 Slot
          </el-button>
        </div>

        <div class="slot-config-scroll">
          <div class="slot-config">
            <div v-for="(slot, idx) in layout.slots_def" :key="idx" class="slot-block">
              <div class="slot-header">
                <span class="slot-label">Slot {{ idx + 1 }}</span>
                <el-button
                  v-if="(layout.slots_def?.length ?? 0) > 1"
                  size="small"
                  type="danger"
                  link
                  @click="onRemoveSlot(idx)"
                >
                  删除
                </el-button>
              </div>
              <div
                v-for="row in slotGroupedRows(slot)"
                :key="`${idx}-${row.port_type}`"
                class="group-row"
              >
                <i class="dot" :style="{ background: PORT_TYPE_COLORS[row.port_type].stroke }" />
                <span>{{ PORT_TYPE_LABELS[row.port_type] }}</span>
                <span>×</span>
                <el-input-number
                  :model-value="row.count"
                  :min="1"
                  :max="128"
                  size="small"
                  @change="(val: number | undefined) => onGroupedCountChange(idx, row.port_type, val)"
                />
                <el-button
                  size="small"
                  type="danger"
                  link
                  :disabled="slotGroupedRows(slot).length <= 1"
                  @click="onRemoveGroupedType(idx, row.port_type)"
                >
                  删除
                </el-button>
              </div>
              <el-button size="small" link type="primary" @click="openAddGroup(idx)">+ 添加接口组</el-button>
            </div>
          </div>
        </div>
      </template>
    </div>

    <div class="editor-toolbar zoom-toolbar">
      <span class="toolbar-label">显示缩放</span>
      <el-button size="small" :disabled="viewZoom <= VIEW_ZOOM_MIN" @click="bumpViewZoom(-VIEW_ZOOM_STEP)">−</el-button>
      <el-slider
        :model-value="viewZoom"
        :min="VIEW_ZOOM_MIN"
        :max="VIEW_ZOOM_MAX"
        :step="VIEW_ZOOM_STEP"
        style="width: 160px; margin: 0 8px"
        @input="onViewZoomChange"
      />
      <el-button size="small" :disabled="viewZoom >= VIEW_ZOOM_MAX" @click="bumpViewZoom(VIEW_ZOOM_STEP)">+</el-button>
      <span class="frame-scale">{{ viewZoom }}%</span>
      <el-button size="small" link type="primary" @click="resetViewZoom">复位</el-button>
      <el-button v-if="layoutCanEdit && !isSwitch && !isServer" size="small" @click="applyLayout">自动适配设备框架</el-button>
      <span v-if="!layoutCanEdit && portsCanEdit" class="toolbar-hint">布局已锁定 · 可点击接口配置对端</span>
    </div>

    <div class="canvas-scroll">
      <!-- Switch front panel -->
      <svg
        v-if="isSwitch && panelView"
        ref="svgRef"
        class="device-svg panel-svg"
        :width="svgDisplayWidth"
        :height="svgDisplayHeight"
        :viewBox="svgViewBox"
      >
        <defs>
          <linearGradient id="panelChassis" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#f4f6f8" />
            <stop offset="100%" stop-color="#d8dee6" />
          </linearGradient>
          <linearGradient id="panelEar" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#b8bfc9" />
            <stop offset="50%" stop-color="#e8ebf0" />
            <stop offset="100%" stop-color="#a8b0bc" />
          </linearGradient>
        </defs>

        <rect
          :x="0"
          y="14"
          :width="svgOffset - 2"
          :height="layout.frame_height"
          rx="2"
          fill="url(#panelEar)"
          stroke="#8a929e"
        />
        <circle :cx="svgOffset / 2 - 1" :cy="28" r="2.5" fill="none" stroke="#606266" />
        <circle :cx="svgOffset / 2 - 1" :cy="14 + layout.frame_height - 14" r="2.5" fill="none" stroke="#606266" />
        <rect
          :x="layout.frame_width + svgOffset + 2"
          y="14"
          :width="svgOffset - 2"
          :height="layout.frame_height"
          rx="2"
          fill="url(#panelEar)"
          stroke="#8a929e"
        />
        <circle :cx="layout.frame_width + svgOffset + svgOffset / 2 + 1" :cy="28" r="2.5" fill="none" stroke="#606266" />
        <circle
          :cx="layout.frame_width + svgOffset + svgOffset / 2 + 1"
          :cy="14 + layout.frame_height - 14"
          r="2.5"
          fill="none"
          stroke="#606266"
        />

        <g :transform="`translate(${svgOffset}, 14)`">
          <rect
            :width="layout.frame_width"
            :height="layout.frame_height"
            rx="3"
            fill="url(#panelChassis)"
            stroke="#4a5562"
            stroke-width="1.5"
          />

          <!-- Core header -->
          <template v-if="panelView.subtype === 'core'">
            <rect :width="layout.frame_width" height="28" fill="#2f3640" />
            <text :x="12" y="18" class="panel-brand">{{ node.name }}</text>
            <text :x="layout.frame_width - 12" y="18" text-anchor="end" class="panel-model">核心机框</text>
          </template>

          <g v-for="zone in panelView.zones" :key="zone.id">
            <rect
              v-if="zone.kind !== 'mgmt'"
              :x="zone.x"
              :y="zone.y"
              :width="zone.w"
              :height="zone.h"
              rx="2"
              class="panel-zone"
              :class="zone.kind"
            />
            <text
              v-if="zone.kind === 'uplink' || zone.kind === 'card'"
              :x="zone.kind === 'card' ? zone.x + 8 : zone.x + zone.w / 2"
              :y="zone.kind === 'card' ? zone.y + 14 : zone.y + 10"
              :text-anchor="zone.kind === 'card' ? 'start' : 'middle'"
              class="zone-label"
            >
              {{ zone.label }}
            </text>

            <!-- Management block -->
            <g v-if="zone.kind === 'mgmt'">
              <text :x="zone.x + 8" :y="zone.y + 16" class="panel-brand">DCIM</text>
              <text :x="zone.x + 8" :y="zone.y + 30" class="panel-model">{{ panelView.modelHint }}</text>
              <rect
                :x="zone.x + 10"
                :y="zone.y + zone.h - 28"
                width="14"
                height="12"
                rx="1"
                fill="#ecf5ff"
                stroke="#409eff"
              />
              <text :x="zone.x + 28" :y="zone.y + zone.h - 19" class="mgmt-label">CONSOLE</text>
              <circle :cx="zone.x + 18" :cy="zone.y + zone.h - 8" r="3" fill="#c0c4cc" stroke="#909399" />
              <text :x="zone.x + 28" :y="zone.y + zone.h - 5" class="mgmt-label">RESET</text>
            </g>
          </g>

          <g
            v-for="port in layout.ports"
            :key="port.id"
            class="port port-interactive"
            :class="{ selected: selectedPortId === port.id, linked: !!port.peer_node_id }"
            @click.stop="onPortClick(port)"
            @dblclick.stop="openPeerDialog(port)"
          >
            <title>{{ port.label }} · 单击选中，双击配置对端</title>
            <rect
              :x="portHitPad(port).x"
              :y="portHitPad(port).y"
              :width="portHitPad(port).w"
              :height="portHitPad(port).h"
              class="port-hit"
              rx="2"
            />
            <path
              :d="portJackPath(port)"
              :fill="portColors(port).fill"
              :stroke="portColors(port).stroke"
              :fill-rule="port.port_type === '10g' ? 'evenodd' : 'nonzero'"
              stroke-width="1.2"
              class="port-face"
            />
            <text
              :x="port.x + port.w / 2"
              :y="portCaptionY(port)"
              text-anchor="middle"
              class="port-label"
            >
              {{ port.label }}
            </text>
            <circle
              v-if="port.peer_node_id"
              :cx="port.x + port.w - 2"
              :cy="port.y + 2"
              r="2.4"
              fill="#67c23a"
              stroke="#fff"
              stroke-width="0.5"
            />
          </g>
        </g>
      </svg>

      <!-- Server front panel -->
      <svg
        v-else-if="isServer && serverFrontPanelView"
        ref="svgRef"
        class="device-svg panel-svg server-panel server-front"
        :width="svgDisplayWidth"
        :height="svgDisplayHeight"
        :viewBox="svgViewBox"
      >
        <defs>
          <linearGradient id="serverFrontChassis" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#eceff3" />
            <stop offset="100%" stop-color="#d5dbe3" />
          </linearGradient>
          <linearGradient id="serverEar" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#6b7380" />
            <stop offset="50%" stop-color="#9aa3b0" />
            <stop offset="100%" stop-color="#5c6572" />
          </linearGradient>
          <pattern id="ventMesh" width="6" height="6" patternUnits="userSpaceOnUse">
            <path d="M0 3 H6 M3 0 V6" stroke="#b0b8c4" stroke-width="0.5" />
          </pattern>
        </defs>
        <rect :x="0" y="14" :width="svgOffset - 2" :height="layout.frame_height" rx="2" fill="url(#serverEar)" stroke="#8a929e" />
        <rect :x="layout.frame_width + svgOffset + 2" y="14" :width="svgOffset - 2" :height="layout.frame_height" rx="2" fill="url(#serverEar)" stroke="#8a929e" />
        <g :transform="`translate(${svgOffset}, 14)`">
          <rect :width="layout.frame_width" :height="layout.frame_height" rx="3" fill="url(#serverFrontChassis)" stroke="#9aa3b0" stroke-width="1.5" />
          <rect :width="layout.frame_width" height="26" fill="#2d3744" />
          <text :x="12" y="17" class="server-title">{{ node.name }} · 前面板 · {{ serverFrontPanelView.title }}</text>
          <!-- Left I/O bezel -->
          <rect x="8" y="32" :width="serverFrontPanelView.formFactor === 1 ? 64 : 80" :height="layout.frame_height - 40" rx="2" fill="#252d38" stroke="#4a5562" />
          <circle :cx="22" :cy="52" r="5" fill="#1a2030" stroke="#606266" />
          <rect x="14" y="64" width="4" height="4" rx="1" fill="#67c23a" />
          <rect x="22" y="64" width="4" height="4" rx="1" fill="#409eff" />
          <rect x="30" y="64" width="4" height="4" rx="1" fill="#e6a23c" />
          <rect v-if="serverFrontPanelView.formFactor !== 1" x="16" y="76" width="10" height="6" rx="1" fill="#303848" stroke="#606266" />
          <rect v-if="serverFrontPanelView.formFactor !== 1" x="28" y="76" width="10" height="6" rx="1" fill="#303848" stroke="#606266" />
          <!-- Side vents -->
          <rect :x="layout.frame_width - 28" y="32" width="20" :height="layout.frame_height - 40" fill="url(#ventMesh)" opacity="0.6" />
          <!-- Drive bays -->
          <g v-for="bay in serverFrontPanelView.driveBays" :key="`${bay.row}-${bay.col}`">
            <rect :x="bay.x" :y="bay.y" :width="bay.w" :height="bay.h" rx="1" fill="#303848" stroke="#606266" stroke-width="1" />
            <rect :x="bay.x + 3" :y="bay.y + bay.h - 8" :width="bay.w - 6" height="4" rx="1" fill="#1a2030" />
            <circle :cx="bay.x + bay.w - 6" :cy="bay.y + 6" r="1.5" fill="#409eff" />
          </g>
        </g>
      </svg>

      <!-- Server rear panel -->
      <svg
        v-else-if="isServer && serverPanelView"
        ref="svgRef"
        class="device-svg panel-svg server-panel"
        :width="svgDisplayWidth"
        :height="svgDisplayHeight"
        :viewBox="svgViewBox"
      >
        <defs>
          <linearGradient id="serverChassis" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#3a414c" />
            <stop offset="100%" stop-color="#2a3038" />
          </linearGradient>
          <linearGradient id="serverEar" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#6b7380" />
            <stop offset="50%" stop-color="#9aa3b0" />
            <stop offset="100%" stop-color="#5c6572" />
          </linearGradient>
          <pattern id="rearVentHex" width="8" height="8" patternUnits="userSpaceOnUse">
            <path d="M4 1 L7 4 L4 7 L1 4 Z" fill="none" stroke="#4a5562" stroke-width="0.6" />
          </pattern>
        </defs>
        <rect :x="0" y="14" :width="svgOffset - 2" :height="layout.frame_height" rx="2" fill="url(#serverEar)" stroke="#8a929e" />
        <rect :x="layout.frame_width + svgOffset + 2" y="14" :width="svgOffset - 2" :height="layout.frame_height" rx="2" fill="url(#serverEar)" stroke="#8a929e" />
        <g :transform="`translate(${svgOffset}, 14)`">
          <rect :width="layout.frame_width" :height="layout.frame_height" rx="3" fill="url(#serverChassis)" stroke="#1f2430" stroke-width="1.5" />
          <rect :width="layout.frame_width" height="26" fill="#1b212a" />
          <text :x="12" y="17" class="server-title">{{ node.name }} · 后面板 · {{ serverPanelView.title }}</text>
          <text :x="layout.frame_width - 12" y="17" text-anchor="end" class="server-sub">扩展卡 {{ serverPanelView.slots.length }}</text>

          <!-- Ventilation -->
          <rect
            :x="serverPanelView.vent.x"
            :y="serverPanelView.vent.y"
            :width="serverPanelView.vent.w"
            :height="serverPanelView.vent.h"
            fill="url(#rearVentHex)"
            opacity="0.55"
          />

          <!-- PSU -->
          <g v-for="psu in serverPanelView.psus" :key="psu.id">
            <rect :x="psu.x" :y="psu.y" :width="psu.w" :height="psu.h" rx="2" class="psu-block" />
            <text :x="psu.x + psu.w / 2" :y="psu.y + psu.h / 2 + 3" text-anchor="middle" class="psu-label">{{ psu.label }}</text>
          </g>

          <!-- Fixed I/O: mgmt / USB / VGA -->
          <rect
            :x="serverPanelView.fixedIo.x"
            :y="serverPanelView.fixedIo.y"
            :width="serverPanelView.fixedIo.w"
            :height="serverPanelView.fixedIo.h"
            rx="2"
            class="fixed-io-block"
          />
          <text :x="serverPanelView.fixedIo.x + 6" :y="serverPanelView.fixedIo.y + 12" class="fixed-io-label">管理口</text>
          <rect :x="serverPanelView.fixedIo.x + 6" :y="serverPanelView.fixedIo.y + 16" width="12" height="10" rx="1" fill="#303848" stroke="#67c23a" />
          <rect :x="serverPanelView.fixedIo.x + 6" :y="serverPanelView.fixedIo.y + 30" width="8" height="5" rx="1" fill="#303848" stroke="#909399" />
          <rect :x="serverPanelView.fixedIo.x + 18" :y="serverPanelView.fixedIo.y + 30" width="8" height="5" rx="1" fill="#303848" stroke="#909399" />
          <rect :x="serverPanelView.fixedIo.x + 30" :y="serverPanelView.fixedIo.y + 22" width="14" height="10" rx="1" fill="#303848" stroke="#909399" />
          <text :x="serverPanelView.fixedIo.x + 37" :y="serverPanelView.fixedIo.y + 30" text-anchor="middle" class="fixed-io-mini">VGA</text>

          <!-- Onboard 1G zone -->
          <rect
            :x="serverPanelView.onboard1gZone.x"
            :y="serverPanelView.onboard1gZone.y"
            :width="serverPanelView.onboard1gZone.w"
            :height="serverPanelView.onboard1gZone.h"
            rx="2"
            class="onboard-zone"
          />
          <text :x="serverPanelView.onboard1gZone.x + 4" :y="serverPanelView.onboard1gZone.y + 10" class="fixed-io-label">板载千兆</text>

          <!-- Expansion zone outline -->
          <rect
            :x="serverPanelView.expansionZone.x - 2"
            :y="serverPanelView.expansionZone.y - 2"
            :width="serverPanelView.expansionZone.w + 4"
            :height="serverPanelView.expansionZone.h + 4"
            rx="2"
            fill="none"
            stroke="rgba(103,194,58,0.25)"
            stroke-dasharray="3 2"
          />

          <!-- Expansion cards (professional PCIe-style) -->
          <g
            v-for="slot in serverPanelView.slots"
            :key="slot.slotIndex"
            class="server-slot"
            :class="{
              draggable: layoutCanEdit,
              dragging: draggingSlot?.slotIndex === slot.slotIndex - 1,
              selected: selectedServerSlotIdx === slot.slotIndex - 1,
            }"
            @mousedown="onServerSlotMouseDown($event, slot)"
          >
            <!-- Outer shadow -->
            <rect
              :x="slot.x + 1"
              :y="slot.y + 1"
              :width="slot.w"
              :height="slot.h"
              rx="2"
              fill="rgba(0,0,0,0.35)"
            />
            <!-- Metal bracket -->
            <rect
              :x="serverCardBracketRects(slot).x"
              :y="serverCardBracketRects(slot).y"
              :width="serverCardBracketRects(slot).w"
              :height="serverCardBracketRects(slot).h"
              :fill="serverCardPalette(slot.kind).bracket"
              stroke="#5c6570"
              stroke-width="0.6"
            />
            <circle
              v-for="(r, ri) in serverCardBracketRects(slot).rivets"
              :key="ri"
              :cx="r.cx"
              :cy="r.cy"
              r="1.4"
              fill="#4a515c"
              stroke="#2a3038"
              stroke-width="0.4"
            />
            <!-- Card face -->
            <rect
              :x="serverCardFaceRect(slot).x"
              :y="serverCardFaceRect(slot).y"
              :width="serverCardFaceRect(slot).w"
              :height="serverCardFaceRect(slot).h"
              rx="1.5"
              :fill="serverCardPalette(slot.kind).face"
              :stroke="serverCardPalette(slot.kind).accent"
              stroke-width="1"
            />
            <rect
              :x="serverCardFaceRect(slot).x + 1"
              :y="serverCardFaceRect(slot).y + 1"
              :width="Math.max(0, serverCardFaceRect(slot).w - 2)"
              height="8"
              rx="1"
              :fill="serverCardPalette(slot.kind).faceDark"
              opacity="0.85"
            />
            <text
              :x="serverCardFaceRect(slot).x + 5"
              :y="serverCardFaceRect(slot).y + 8"
              class="server-slot-label"
              :fill="serverCardPalette(slot.kind).label"
            >
              {{ slot.shortLabel }} · {{ slot.slotIndex }}
            </text>
            <!-- Blank / RAID filler details -->
            <g v-if="slot.kind === 'blank' || slot.kind === 'raid'">
              <line
                v-for="(m, mi) in serverBlankFillerMarks(slot)"
                :key="mi"
                :x1="m.x1"
                :y1="m.y1"
                :x2="m.x2"
                :y2="m.y2"
                stroke="rgba(255,255,255,0.08)"
                stroke-width="1"
              />
              <text
                :x="slot.x + slot.w / 2"
                :y="slot.y + slot.h / 2 + 3"
                text-anchor="middle"
                class="raid-mark"
              >
                {{ slot.kind === 'blank' ? '挡板' : 'RAID' }}
              </text>
            </g>
            <!-- Selection outline -->
            <rect
              v-if="selectedServerSlotIdx === slot.slotIndex - 1"
              :x="slot.x - 1"
              :y="slot.y - 1"
              :width="slot.w + 2"
              :height="slot.h + 2"
              rx="2.5"
              fill="none"
              stroke="#409eff"
              stroke-width="1.2"
              stroke-dasharray="3 2"
            />
            <!-- Resize handle -->
            <g
              v-if="layoutCanEdit"
              class="resize-handle"
              @mousedown="onServerSlotResizeMouseDown($event, slot)"
            >
              <rect
                :x="slot.x + slot.w - SERVER_RESIZE_HANDLE"
                :y="slot.y + slot.h - SERVER_RESIZE_HANDLE"
                :width="SERVER_RESIZE_HANDLE"
                :height="SERVER_RESIZE_HANDLE"
                rx="1.5"
                fill="#409eff"
                opacity="0.85"
              />
              <path
                :d="`M ${slot.x + slot.w - 8} ${slot.y + slot.h - 3} L ${slot.x + slot.w - 3} ${slot.y + slot.h - 3} L ${slot.x + slot.w - 3} ${slot.y + slot.h - 8} Z`"
                fill="#fff"
                opacity="0.9"
              />
            </g>
          </g>

          <!-- Ports -->
          <g
            v-for="port in layout.ports"
            :key="port.id"
            class="port port-interactive"
            :class="{ selected: selectedPortId === port.id, linked: !!port.peer_node_id, locked: port.layout_locked }"
            @mousedown="onServerPortMouseDown($event, port)"
            @click.stop="onPortClick(port)"
            @dblclick.stop="openPeerDialog(port)"
          >
            <title>{{ port.label }} · 单击选中，双击配置对端</title>
            <rect
              :x="portHitPad(port).x"
              :y="portHitPad(port).y"
              :width="portHitPad(port).w"
              :height="portHitPad(port).h"
              class="port-hit"
              rx="2"
            />
            <path
              :d="portJackPath(port)"
              :fill="portColors(port).fill"
              :stroke="portColors(port).stroke"
              :fill-rule="port.port_type === '10g' ? 'evenodd' : 'nonzero'"
              stroke-width="1.4"
              class="port-face"
            />
            <text
              :x="port.x + port.w / 2"
              :y="port.y + port.h + 8"
              text-anchor="middle"
              class="port-label"
            >
              {{ port.label }}
            </text>
            <circle
              v-if="port.peer_node_id"
              :cx="port.x + port.w - 2"
              :cy="port.y + 2"
              r="2.4"
              fill="#67c23a"
              stroke="#fff"
              stroke-width="0.5"
            />
            <g
              v-if="portsCanEdit && selectedPortId === port.id"
              class="port-edit-badge"
              @click.stop="openPeerDialog(port)"
            >
              <rect
                :x="port.x + port.w / 2 - 14"
                :y="port.y - 14"
                width="28"
                height="12"
                rx="2"
                fill="#409eff"
              />
              <text
                :x="port.x + port.w / 2"
                :y="port.y - 5"
                text-anchor="middle"
                class="port-edit-badge-text"
              >
                配置
              </text>
            </g>
          </g>
        </g>
      </svg>

      <!-- Legacy security editor -->
      <svg
        v-else
        ref="svgRef"
        class="device-svg"
        :width="svgDisplayWidth"
        :height="svgDisplayHeight"
        :viewBox="svgViewBox"
      >
        <defs>
          <linearGradient id="chassisGrad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#eef1f6" />
            <stop offset="45%" stop-color="#f8f9fb" />
            <stop offset="100%" stop-color="#dfe4ec" />
          </linearGradient>
          <linearGradient id="earGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#c8ced8" />
            <stop offset="50%" stop-color="#e2e6ed" />
            <stop offset="100%" stop-color="#b8bec8" />
          </linearGradient>
          <linearGradient id="bezelGrad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#3a4555" />
            <stop offset="100%" stop-color="#252d38" />
          </linearGradient>
        </defs>

        <rect
          :x="0"
          y="14"
          :width="svgOffset - 2"
          :height="layout.frame_height"
          rx="2"
          fill="url(#earGrad)"
          stroke="#909399"
          stroke-width="1"
        />
        <rect
          :x="layout.frame_width + svgOffset + 2"
          y="14"
          :width="svgOffset - 2"
          :height="layout.frame_height"
          rx="2"
          fill="url(#earGrad)"
          stroke="#909399"
          stroke-width="1"
        />

        <g :transform="`translate(${svgOffset}, 14)`">
          <rect
            :width="layout.frame_width"
            :height="layout.frame_height"
            rx="4"
            fill="url(#chassisGrad)"
            stroke="#606266"
            stroke-width="1.5"
          />
          <rect :width="layout.frame_width" :height="FRAME_HEADER_PX" rx="4" fill="url(#bezelGrad)" />
          <text
            :x="layout.frame_width / 2"
            :y="FRAME_HEADER_PX / 2 + 4"
            text-anchor="middle"
            class="device-title"
          >
            {{ node.name }} · {{ NODE_KIND_LABELS[node.kind] }} · {{ formatDeviceFrameLabel(layout) }}
          </text>

          <g
            v-for="(band, idx) in slotBands"
            :key="`band-${idx}`"
            class="slot-band-group"
            :class="{
              selected: selectedGroupId === `slot-${band.slotIndex}`,
              dragging: draggingSlot?.slotIndex === band.slotIndex - 1,
            }"
          >
            <rect :x="band.x" :y="band.y" :width="band.w" :height="band.h" rx="3" class="slot-band" />
            <rect
              :x="band.x"
              :y="band.y"
              :width="band.w"
              height="16"
              class="slot-drag-handle"
              @mousedown="onSlotMouseDown($event, band)"
            />
            <text :x="band.x + band.w / 2" :y="band.y + 12" text-anchor="middle" class="slot-band-label">
              {{ band.label }}
            </text>
            <text :x="band.x + band.w / 2" :y="band.y + band.h - 4" text-anchor="middle" class="slot-meta">
              {{ slotWidthMm(band) }}mm
            </text>
          </g>

          <g
            v-for="group in groupLayouts"
            :key="group.groupId"
            class="port-group"
            :class="{ selected: selectedGroupId === group.groupId, dragging: draggingGroup?.groupId === group.groupId }"
            @mousedown="onGroupMouseDown($event, group)"
            @click.stop="onGroupClick(group.groupId)"
          >
            <rect
              :x="group.x"
              :y="group.y"
              :width="group.w"
              :height="group.h"
              rx="3"
              class="group-bg"
              :stroke="groupColors(group.portType).stroke"
            />
            <text :x="group.x + 4" :y="group.y + 8" class="group-label">{{ group.label }}</text>
          </g>

          <g
            v-for="port in layout.ports"
            :key="port.id"
            class="port port-interactive"
            :class="{ selected: selectedPortId === port.id, linked: !!port.peer_node_id }"
            @click.stop="onPortClick(port)"
            @dblclick.stop="openPeerDialog(port)"
          >
            <title>{{ port.label }} · 单击选中，双击配置对端</title>
            <rect
              :x="portHitPad(port).x"
              :y="portHitPad(port).y"
              :width="portHitPad(port).w"
              :height="portHitPad(port).h"
              class="port-hit"
              rx="2"
            />
            <path
              :d="portJackPath(port)"
              :fill="portColors(port).fill"
              :stroke="portColors(port).stroke"
              :fill-rule="port.port_type === '10g' ? 'evenodd' : 'nonzero'"
              stroke-width="1.2"
              class="port-face"
            />
            <text :x="port.x + port.w / 2" :y="port.y + port.h + 8" text-anchor="middle" class="port-label">
              {{ port.label }}
            </text>
            <circle
              v-if="port.peer_node_id"
              :cx="port.x + port.w - 3"
              :cy="port.y + 3"
              r="2.5"
              fill="#67c23a"
              stroke="#fff"
              stroke-width="0.5"
            />
          </g>
        </g>
      </svg>
    </div>

    <div v-if="selectedPort" class="port-info">
      <span>
        {{ selectedPort.label }} · {{ PORT_TYPE_LABELS[selectedPort.port_type || '1g'] }}
        · Slot {{ selectedPort.slot_index }}
      </span>
      <el-button v-if="portsCanEdit" type="primary" @click="openPortEdit(selectedPort)">编辑标签</el-button>
      <el-button v-if="portsCanEdit" type="primary" @click="openPeerDialog(selectedPort)">配置对端</el-button>
      <span v-if="selectedPort?.peer_node_id" class="peer-hint">
        → {{ peerNodes.find((n) => n.id === selectedPort!.peer_node_id)?.name || '未知' }}
        · {{ formatNodeLocation(peerNodes.find((n) => n.id === selectedPort!.peer_node_id) || props.node) }}
        / {{ selectedPort!.peer_port }}
      </span>
    </div>
    <p v-else-if="isServer" class="hint">
      <template v-if="layoutCanEdit">
        后面板：拖动扩展卡移动/缩放；网口可拖动调整位置；单击选中接口，双击或点「配置对端」编辑
      </template>
      <template v-else>
        布局已锁定：单击选中扩展卡/板载接口，双击或使用下方按钮配置对端
      </template>
    </p>
    <p v-else class="hint">
      <template v-if="layoutCanEdit">单击接口选中，双击配置对端；调整上方数量/上联位置后面板自动更新</template>
      <template v-else>布局已锁定：单击选中接口，双击或点「配置对端」编辑连接</template>
    </p>

    <el-dialog v-model="addSlotVisible" :title="isServer ? '添加服务器 Slot' : '添加 Slot'" width="420px" append-to-body>
      <el-form label-width="96px">
        <template v-if="isServer">
          <el-form-item label="Slot 类型">
            <el-select v-model="addForm.server_slot_kind" style="width: 100%">
              <el-option
                v-for="(label, key) in SERVER_SLOT_KIND_LABELS"
                :key="key"
                :label="label"
                :value="key"
              />
            </el-select>
          </el-form-item>
          <el-form-item v-if="!isPortlessServerSlot(addForm.server_slot_kind)" label="接口数量">
            <el-input-number
              v-model="addForm.count"
              :min="1"
              :max="SERVER_SLOT_PORT_MAX"
              @change="(val: number | undefined) => { if (val != null) addForm.count = normalizeServerSlotPortCount(val) }"
            />
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="接口类型">
            <el-select v-model="addForm.port_type" style="width: 100%">
              <el-option v-for="(label, key) in PORT_TYPE_LABELS" :key="key" :label="label" :value="key" />
            </el-select>
          </el-form-item>
          <el-form-item label="接口数量">
            <el-input-number v-model="addForm.count" :min="1" :max="32" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="addSlotVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmAddSlot">添加</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="addGroupVisible" title="添加接口组" width="400px" append-to-body>
      <el-form label-width="88px">
        <el-form-item label="所属 Slot">
          <el-tag>Slot {{ addGroupSlotIdx + 1 }}</el-tag>
        </el-form-item>
        <el-form-item label="接口类型">
          <el-select v-model="addForm.port_type" style="width: 100%">
            <el-option v-for="(label, key) in PORT_TYPE_LABELS" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="接口数量">
          <el-input-number v-model="addForm.count" :min="1" :max="32" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addGroupVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmAddGroup">添加</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="portEditVisible" title="编辑接口标签" width="380px" append-to-body>
      <el-form label-width="88px">
        <el-form-item label="显示标签">
          <el-input v-model="portForm.label" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="portEditVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmPortEdit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="peerVisible" title="对端接口信息" width="560px" append-to-body>
      <el-form label-width="96px">
        <el-form-item label="当前接口">
          <el-tag>{{ selectedPort?.label }} ({{ PORT_TYPE_LABELS[selectedPort?.port_type || '1g'] }})</el-tag>
        </el-form-item>
        <el-form-item label="对端设备">
          <el-select v-model="peerForm.peer_node_id" clearable filterable style="width: 100%">
            <el-option
              v-for="n in peerNodes"
              :key="n.id"
              :label="`${n.name} · ${formatNodeLocation(n)}`"
              :value="n.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="selectedPeerNode" label="设备位置">
          <span class="location-text">{{ formatNodeLocation(selectedPeerNode) }}</span>
        </el-form-item>
        <el-form-item label="对端接口">
          <el-select
            v-model="peerForm.peer_port"
            clearable
            filterable
            :disabled="!peerForm.peer_node_id"
            style="width: 100%"
          >
            <el-option v-for="p in peerPortOptions" :key="p.id" :label="p.label" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="连接备注">
          <el-input v-model="peerForm.peer_label" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="clearPeer">清除对端</el-button>
        <el-button @click="peerVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmPeer">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.frame-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}

.config-panel {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 10px 12px;
  background: #fafafa;
}

.switch-config {
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px dashed #dcdfe6;
}

.card-editor {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}

.card-editor-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.card-editor-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.card-editor-hint {
  color: #909399;
  font-size: 12px;
}

.location-text {
  color: #606266;
  font-size: 13px;
}

.panel-svg .panel-zone {
  fill: rgba(255, 255, 255, 0.35);
  stroke: rgba(96, 98, 102, 0.25);
  stroke-width: 1;
}

.panel-svg .panel-zone.uplink {
  fill: rgba(230, 162, 60, 0.08);
  stroke: rgba(230, 162, 60, 0.45);
}

.panel-svg .panel-zone.card {
  fill: rgba(255, 255, 255, 0.55);
  stroke: rgba(64, 158, 255, 0.35);
}

.panel-brand {
  font-size: 11px;
  font-weight: 700;
  fill: #303133;
}

.panel-model {
  font-size: 8px;
  fill: #909399;
}

.mgmt-label {
  font-size: 7px;
  fill: #606266;
}

.zone-label {
  font-size: 8px;
  font-weight: 600;
  fill: #606266;
}

.panel-svg .port-label {
  font-size: 6.5px;
  fill: #606266;
}

.server-panel .server-title {
  font-size: 11px;
  font-weight: 600;
  fill: #e8ecf2;
}

.server-panel .server-sub {
  font-size: 9px;
  fill: #9aa3b0;
}

.server-slot-bg {
  fill: rgba(255, 255, 255, 0.08);
  stroke: rgba(180, 190, 205, 0.45);
  stroke-width: 1;
}

.server-slot-bg.nic_1g {
  fill: rgba(64, 158, 255, 0.12);
  stroke: rgba(64, 158, 255, 0.55);
}

.server-slot-bg.nic_10g {
  fill: rgba(103, 194, 58, 0.12);
  stroke: rgba(103, 194, 58, 0.55);
}

.server-slot-bg.hba {
  fill: rgba(230, 162, 60, 0.12);
  stroke: rgba(230, 162, 60, 0.55);
}

.server-slot-bg.raid {
  fill: rgba(144, 147, 153, 0.18);
  stroke: rgba(192, 196, 204, 0.55);
}

.server-slot-bg.blank {
  fill: rgba(60, 64, 72, 0.35);
  stroke: rgba(140, 145, 155, 0.45);
  stroke-dasharray: 4 3;
}

.server-slot.draggable {
  cursor: grab;
}

.server-slot:not(.draggable) {
  pointer-events: none;
}

.server-slot.dragging {
  cursor: grabbing;
}

.server-slot.selected .resize-handle {
  opacity: 1;
}

.resize-handle {
  cursor: nwse-resize;
}

.server-slot-label {
  font-size: 8px;
  font-weight: 600;
  pointer-events: none;
}

.fixed-io-block {
  fill: rgba(0, 0, 0, 0.25);
  stroke: rgba(144, 147, 153, 0.45);
}

.onboard-zone {
  fill: rgba(103, 194, 58, 0.08);
  stroke: rgba(103, 194, 58, 0.35);
}

.fixed-io-label {
  font-size: 7px;
  fill: #aeb6c2;
}

.fixed-io-mini {
  font-size: 6px;
  fill: #909399;
}

.drag-hint {
  margin: 4px 0 0;
  font-size: 11px;
  color: #909399;
}

.port.locked path {
  stroke-dasharray: 2 1;
}

.raid-mark {
  font-size: 11px;
  font-weight: 700;
  fill: #c0c4cc;
}

.psu-block {
  fill: rgba(0, 0, 0, 0.35);
  stroke: rgba(180, 190, 205, 0.4);
}

.psu-label {
  font-size: 8px;
  fill: #aeb6c2;
}

.server-slot-block {
  min-width: 180px;
}

.raid-hint {
  font-size: 12px;
  color: #909399;
}

.config-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin-bottom: 10px;
  font-size: 13px;
}

.config-row label {
  color: #606266;
}

.field-hint {
  color: #909399;
  font-size: 12px;
}

.slot-config-scroll {
  overflow-x: auto;
  margin: 0 -4px;
  padding: 0 4px 4px;
}

.slot-config {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: 10px;
  min-width: min-content;
}

.slot-block {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 8px 10px;
  background: #fff;
  min-width: 200px;
  max-width: 280px;
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.slot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.slot-label {
  font-weight: 600;
  font-size: 13px;
}

.group-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 4px 0 4px 6px;
  border-left: 3px solid #e4e7ed;
}

.type-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 10px;
  font-size: 12px;
  color: #606266;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  display: inline-block;
}

.editor-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.zoom-toolbar {
  margin-bottom: 4px;
}

.toolbar-label {
  font-size: 13px;
  color: #606266;
}

.toolbar-hint {
  margin-left: 8px;
  font-size: 12px;
  color: #909399;
}

.frame-size,
.frame-scale {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #606266;
}

.canvas-scroll {
  overflow: auto;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: linear-gradient(180deg, #eef2f7 0%, #f5f7fa 100%);
  flex: 1;
  min-height: 320px;
  padding: 8px;
}

.device-svg {
  display: block;
  margin: 0 auto;
}

.device-title {
  font-size: 11px;
  font-weight: 600;
  fill: #e8eaed;
}

.slot-band {
  fill: rgba(255, 255, 255, 0.35);
  stroke: rgba(96, 98, 102, 0.2);
  stroke-width: 1;
}

.slot-band-group.dragging .slot-band,
.slot-band-group.selected .slot-band {
  stroke: #409eff;
  stroke-width: 1.5;
}

.slot-drag-handle {
  fill: rgba(64, 158, 255, 0.08);
  cursor: grab;
}

.slot-band-group.dragging .slot-drag-handle {
  cursor: grabbing;
  fill: rgba(64, 158, 255, 0.18);
}

.slot-divider-v {
  stroke: rgba(96, 98, 102, 0.25);
  stroke-width: 1;
}

.slot-band-label {
  font-size: 9px;
  font-weight: 600;
  fill: #606266;
}

.port-group {
  cursor: grab;
}

.port-group.dragging {
  cursor: grabbing;
}

.port-group.selected .group-bg {
  stroke-width: 2;
  filter: drop-shadow(0 1px 4px rgba(64, 158, 255, 0.35));
}

.group-bg {
  fill: rgba(255, 255, 255, 0.55);
  stroke-width: 1.2;
  stroke-dasharray: 4 2;
}

.group-label {
  font-size: 7px;
  fill: #606266;
  pointer-events: none;
}

.port {
  cursor: pointer;
}

.port-interactive .port-hit {
  fill: transparent;
  stroke: transparent;
  pointer-events: all;
}

.port-interactive:hover .port-hit {
  fill: rgba(64, 158, 255, 0.18);
  stroke: rgba(64, 158, 255, 0.55);
  stroke-width: 1;
}

.port-interactive.selected .port-hit {
  fill: rgba(64, 158, 255, 0.28);
  stroke: #409eff;
  stroke-width: 1.2;
}

.port-interactive .port-face {
  pointer-events: none;
}

.port-edit-badge {
  cursor: pointer;
}

.port-edit-badge-text {
  font-size: 8px;
  font-weight: 700;
  fill: #fff;
  pointer-events: none;
}

.port.selected path.port-face,
.port.selected path:not(.port-hit) {
  stroke-width: 2;
  filter: drop-shadow(0 0 2px rgba(64, 158, 255, 0.45));
}

.port.linked path.port-face {
  stroke-width: 1.8;
}

.port-label {
  font-size: 7px;
  fill: #303133;
  pointer-events: none;
}

.port-info {
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 8px 10px;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
}

.peer-hint {
  color: #67c23a;
}

.hint {
  margin: 0;
  font-size: 12px;
  color: #909399;
}
</style>
