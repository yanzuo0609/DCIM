<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  CORE_CARD_TYPE_LABELS,
  NODE_KIND_LABELS,
  PORT_TYPE_COLORS,
  PORT_TYPE_LABELS,
  PORT_TYPE_SHORT,
  SERVER_ORIENTATION_LABELS,
  SERVER_SLOT_KIND_LABELS,
  SECURITY_ZONE_LAYOUT_LABELS,
  SWITCH_SUBTYPE_DEFAULTS,
  SWITCH_SUBTYPE_LABELS,
  UPLINK_POSITION_LABELS,
  formatNodeLocation,
  listNodePortOptions,
  newCoreLineCard,
  serverSlotDefaultPortType,
  type CoreCardType,
  type CoreLineCard,
  type FramePort,
  type LayoutSlotDef,
  type NetworkNode,
  type PortLayout,
  type PortType,
  type SecurityZoneLayout,
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
  applySecurityLayoutConfig,
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
  moveSecurityZoneInPanel,
  resizeSecurityZoneInPanel,
  resetSecurityZonePositions,
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
import {
  SEC_EAR,
  SEC_FRAME_HEIGHT_BY_U,
  SEC_RESIZE_HANDLE,
  layoutSecurityFrontPanel,
  normalizeSecurityHeightU,
  newSecurityZoneSlot,
  patchSecurityZoneSlot,
  type SecurityPanelView,
} from '@/utils/securityFrontPanel'
import { listDevices, type Device } from '@/api/device'
import type { PortLayout as DevicePortLayout } from '@/api/network'

const props = defineProps<{
  node: NetworkNode
  peerNodes: NetworkNode[]
  /** 是否可配置接口（对端/标签） */
  editable?: boolean
  /** 是否可编辑布局结构（拖动卡槽、改数量等）；默认与 editable 相同 */
  layoutEditable?: boolean
}>()

/**
 * 布局结构是否可改（添加/编辑/删除扩展卡、拖动等）。
 * 保存后 layout_locked=true，须点「编辑布局」才可改。
 */
const layoutCanEdit = computed(() => {
  if (!(props.editable ?? false)) return false
  if (props.node.port_layout?.layout_locked === true) return false
  if (typeof props.layoutEditable === 'boolean') return props.layoutEditable
  return true
})
const portsCanEdit = computed(() => props.editable ?? false)

/** 每个节点只做一次布局归一化，避免 computed 反复副作用拖慢渲染 */
const layoutReadyNodeId = ref<string | null>(null)

function ensureNodePortLayout() {
  const node = props.node
  if (!node.port_layout) {
    node.port_layout = defaultPortLayout(node.kind)
    if (node.kind === 'switch') {
      applySwitchLayoutConfig(node.port_layout, {
        subtype: 'gigabit',
        mainPortCount: 48,
        uplinkPortCount: 4,
        uplinkPosition: 'right',
      })
    } else if (node.kind === 'server') {
      applyServerFormFactor(node.port_layout, 1)
      syncPortsFromSlotsDef(node.port_layout, false)
    } else if (node.kind === 'security') {
      applySecurityLayoutConfig(node.port_layout, {
        heightU: node.port_layout.height_u ?? 1,
        preservePeers: false,
      })
    } else {
      syncPortsFromSlotsDef(node.port_layout, false)
    }
  } else if (layoutReadyNodeId.value !== node.id) {
    normalizePortLayout(node.port_layout)
    if (node.kind === 'switch' && !node.port_layout.switch_subtype) {
      applySwitchLayoutConfig(node.port_layout, {
        subtype: 'gigabit',
        mainPortCount: node.port_layout.main_port_count ?? 48,
        uplinkPortCount: node.port_layout.uplink_port_count ?? 4,
        uplinkPosition: node.port_layout.uplink_position ?? 'right',
      })
    } else if (node.kind === 'server' && node.port_layout.server_form_factor == null) {
      applyServerFormFactor(
        node.port_layout,
        normalizeServerFormFactor(node.port_layout.height_u ?? 1),
      )
      syncPortsFromSlotsDef(node.port_layout, true)
    } else if (node.kind === 'security') {
      const h = normalizeSecurityHeightU(node.port_layout.height_u)
      const expectedH = SEC_FRAME_HEIGHT_BY_U[h]
      if (
        !node.port_layout.security_panel
        || Math.round(node.port_layout.frame_height) !== expectedH
        || node.port_layout.height_u !== h
      ) {
        applySecurityLayoutConfig(node.port_layout, { heightU: h, preservePeers: true })
      }
    } else if (!node.port_layout.ports.length) {
      syncPortsFromSlotsDef(node.port_layout, false)
    }
  }
  layoutReadyNodeId.value = node.id
}

const layout = computed(() => {
  ensureNodePortLayout()
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
const regionEditorVisible = ref(false)
const regionEditorMode = ref<'add' | 'edit'>('add')
const regionEditorIndex = ref<number | null>(null)
const panelView = ref<ReturnType<typeof layoutSwitchFrontPanel> | null>(null)
const serverPanelView = ref<ServerPanelView | null>(null)
const serverFrontPanelView = ref<ServerFrontPanelView | null>(null)
const securityPanelView = ref<SecurityPanelView | null>(null)

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

/** 扩展卡 / 接口区统一编辑表单 */
const regionForm = reactive({
  server_slot_kind: 'nic_10g' as ServerSlotKind,
  orientation: 'horizontal' as ServerSlotOrientation,
  layout_w: 120,
  layout_h: 40,
  count: 2,
  zone_label: '',
  port_type: '1g' as PortType,
  zone_layout: 'auto' as SecurityZoneLayout,
})

const switchForm = reactive({
  subtype: 'gigabit' as SwitchSubtype,
  main_port_count: 48,
  uplink_port_count: 4,
  uplink_position: 'right' as UplinkPosition,
  optical_card_count: 1,
  optical_ports_per_card: 48,
  line_cards: [newCoreLineCard()] as CoreLineCard[],
})

const serverForm = reactive({
  form_factor: 1 as ServerFormFactor,
  onboard_1g_count: 4,
})

const peerForm = reactive({
  source: 'define' as 'define' | 'inventory',
  peer_node_id: '' as string | null,
  peer_port: '' as string | null,
  peer_label: '',
  peer_device_id: '' as string | null,
  peer_device_name: '' as string | null,
})

const inventoryDevices = ref<Device[]>([])
const inventoryLoading = ref(false)

const portForm = reactive({
  label: '',
})

const isSwitch = computed(() => props.node.kind === 'switch')
const isServer = computed(() => props.node.kind === 'server')
const isSecurity = computed(() => props.node.kind === 'security')
const isCoreSwitch = computed(() => isSwitch.value && switchForm.subtype === 'core')
const isGigabitSwitch = computed(() => isSwitch.value && switchForm.subtype === 'gigabit')
const isTenGigabitSwitch = computed(() => isSwitch.value && switchForm.subtype === 'ten_gigabit')
const isAggregationSwitch = computed(() => isSwitch.value && switchForm.subtype === 'aggregation')

const slotBands = computed(() =>
  isSwitch.value || isServer.value || isSecurity.value ? [] : slotBandRects(layout.value),
)
const groupLayouts = computed(() =>
  isSwitch.value || isServer.value || isSecurity.value ? [] : groupVisualLayouts(layout.value),
)
const svgOffset = computed(() =>
  isSwitch.value || isServer.value || isSecurity.value ? (isSecurity.value ? SEC_EAR + 6 : PANEL_EAR + 6) : EAR_WIDTH_PX + 6,
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
  if (isSecurity.value) return 90
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

function refreshSecurityPanel() {
  if (!isSecurity.value) {
    securityPanelView.value = null
    return
  }
  layout.value.security_panel = true
  if (!layout.value.slots_def?.length) {
    applySecurityLayoutConfig(layout.value, { preservePeers: false })
  } else {
    syncPortsFromSlotsDef(layout.value, true)
    securityPanelView.value = layoutSecurityFrontPanel(layout.value)
    return
  }
  securityPanelView.value = layoutSecurityFrontPanel(layout.value)
}

function onSecurityHeightChange(val: number | string | undefined) {
  if (val == null || !layoutCanEdit.value) return
  const next = normalizeSecurityHeightU(val)
  layout.value.height_u = next
  layout.value.security_panel = true
  applySecurityLayoutConfig(layout.value, { heightU: next, preservePeers: true })
  securityPanelView.value = layoutSecurityFrontPanel(layout.value)
  syncLegacyFromPortLayout(props.node)
}

function onSecurityZoneChange(
  slotIdx: number,
  patch: Partial<{
    label: string
    port_type: PortType
    count: number
    zone_layout: SecurityZoneLayout
    layout_w: number
    layout_h: number
  }>,
) {
  if (!layoutCanEdit.value) return
  const slot = layout.value.slots_def?.[slotIdx]
  if (!slot) return
  patchSecurityZoneSlot(slot, slotIdx, patch)
  ;(layout.value.ports || [])
    .filter((p) => p.slot_index === slotIdx + 1)
    .forEach((p) => { p.layout_locked = false })
  syncPortsFromSlotsDef(layout.value, true)
  securityPanelView.value = layoutSecurityFrontPanel(layout.value)
  syncLegacyFromPortLayout(props.node)
}

function onResetSecurityZoneLayout() {
  if (!layoutCanEdit.value) return
  resetSecurityZonePositions(layout.value)
  securityPanelView.value = layoutSecurityFrontPanel(layout.value)
  syncLegacyFromPortLayout(props.node)
}

function onRemoveSecurityZone(slotIdx: number) {
  if (!layoutCanEdit.value || !layout.value.slots_def) return
  if (layout.value.slots_def.length <= 1) return
  layout.value.slots_def.splice(slotIdx, 1)
  layout.value.slot_count = layout.value.slots_def.length
  syncPortsFromSlotsDef(layout.value, true)
  securityPanelView.value = layoutSecurityFrontPanel(layout.value)
  syncLegacyFromPortLayout(props.node)
}

function syncServerFormFromLayout() {
  if (!isServer.value) return
  serverForm.form_factor = normalizeServerFormFactor(layout.value.server_form_factor ?? layout.value.height_u ?? 1)
  serverForm.onboard_1g_count = layout.value.server_onboard_1g_count ?? 4
}

const selectedPort = computed(() =>
  layout.value.ports.find((p) => p.id === selectedPortId.value) || null,
)

function asDevicePortLayout(layout: Record<string, unknown> | null | undefined): DevicePortLayout | null {
  if (!layout || !Array.isArray(layout.ports)) return null
  return layout as unknown as DevicePortLayout
}

const peerPortOptions = computed(() => {
  if (peerForm.source === 'inventory') {
    if (!peerForm.peer_device_id) return []
    const device = inventoryDevices.value.find((d) => d.id === peerForm.peer_device_id)
    const layout = asDevicePortLayout(device?.port_layout)
    const ports = layout?.ports || []
    return ports.map((p) => ({
      id: p.id,
      label: `${p.label} (${PORT_TYPE_LABELS[p.port_type] || p.port_type})`,
    }))
  }
  if (!peerForm.peer_node_id) return []
  const peer = props.peerNodes.find((n) => n.id === peerForm.peer_node_id)
  return peer ? listNodePortOptions(peer) : []
})

const selectedPeerNode = computed(() =>
  props.peerNodes.find((n) => n.id === peerForm.peer_node_id) || null,
)

const selectedInventoryDevice = computed(
  () => inventoryDevices.value.find((d) => d.id === peerForm.peer_device_id) || null,
)

const peerHintText = computed(() => {
  const port = selectedPort.value
  if (!port) return ''
  if (port.peer_device_id) {
    return `→ 台账 ${port.peer_device_name || port.peer_device_id} / ${port.peer_port || '—'}`
  }
  if (port.peer_node_id) {
    const n = props.peerNodes.find((x) => x.id === port.peer_node_id)
    return `→ ${n?.name || '未知'} · ${formatNodeLocation(n || props.node)} / ${port.peer_port || '—'}`
  }
  return ''
})

async function loadInventoryDevices() {
  inventoryLoading.value = true
  try {
    const data = await listDevices({ page: 1, page_size: 200, network_panel_bound: true })
    const items = (data.items || []) as Device[]
    inventoryDevices.value = items.filter((d) => {
      const layout = asDevicePortLayout(d.port_layout)
      return !!d.network_panel_bound && !!layout && (layout.ports?.length || 0) > 0
    })
    if (!inventoryDevices.value.length) {
      // 回退：拉一页台账再前端过滤
      const all = await listDevices({ page: 1, page_size: 200 })
      inventoryDevices.value = ((all.items || []) as Device[]).filter((d) => {
        const layout = asDevicePortLayout(d.port_layout)
        return !!d.network_panel_bound && !!layout && (layout.ports?.length || 0) > 0
      })
    }
  } catch {
    inventoryDevices.value = []
    ElMessage.error('加载已绑定面板的台账设备失败')
  } finally {
    inventoryLoading.value = false
  }
}

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
const selectedSecurityZoneIdx = ref<number | null>(null)
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
  refreshSecurityPanel()
}

function syncSwitchFormFromLayout() {
  if (!isSwitch.value) return
  const config = readSwitchLayoutConfig(layout.value)
  switchForm.subtype = config.subtype
  switchForm.main_port_count = config.mainPortCount
  switchForm.uplink_port_count = config.uplinkPortCount
  switchForm.uplink_position = config.uplinkPosition
  if (
    config.subtype === 'gigabit' ||
    config.subtype === 'ten_gigabit' ||
    config.subtype === 'aggregation'
  ) {
    const cards = Math.max(1, switchForm.optical_card_count || 1)
    const ppc = Math.max(1, Math.floor(config.mainPortCount / cards) || 48)
    switchForm.optical_card_count = cards
    switchForm.optical_ports_per_card = ppc
    switchForm.main_port_count = cards * ppc
  }
  switchForm.line_cards = config.lineCards?.length
    ? config.lineCards.map((c) => ({ ...c }))
    : [newCoreLineCard()]
}

function onSwitchSubtypeChange(subtype: SwitchSubtype) {
  const defaults = SWITCH_SUBTYPE_DEFAULTS[subtype]
  switchForm.main_port_count = defaults.mainPortCount
  switchForm.uplink_port_count = defaults.uplinkPortCount
  if (subtype === 'gigabit' || subtype === 'ten_gigabit' || subtype === 'aggregation') {
    switchForm.optical_card_count = 1
    switchForm.optical_ports_per_card = defaults.mainPortCount
  }
  if (subtype === 'core' && !switchForm.line_cards.length) {
    switchForm.line_cards = [newCoreLineCard()]
  }
}

function syncAccessSwitchMainFromCards() {
  const cards = Math.max(1, Math.min(16, switchForm.optical_card_count || 1))
  const ppc = Math.max(1, Math.min(128, switchForm.optical_ports_per_card || 48))
  switchForm.optical_card_count = cards
  switchForm.optical_ports_per_card = ppc
  switchForm.main_port_count = Math.max(1, Math.min(256, cards * ppc))
}

function onAccessSwitchCardChange() {
  syncAccessSwitchMainFromCards()
  onSwitchFormChange()
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

function onEditorLineCardTypeChange(card: CoreLineCard) {
  if (card.card_type === 'blank') card.port_count = 0
  else if (!card.port_count || card.port_count < 1) card.port_count = 48
  onSwitchFormChange()
}

function applySwitchTemplate() {
  if (
    switchForm.subtype === 'gigabit' ||
    switchForm.subtype === 'ten_gigabit' ||
    switchForm.subtype === 'aggregation'
  ) {
    syncAccessSwitchMainFromCards()
  }
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

const regionItemLabel = computed(() => (isSecurity.value ? '接口区' : '扩展卡'))

const regionEditorTitle = computed(() => {
  const label = regionItemLabel.value
  return regionEditorMode.value === 'add' ? `添加${label}` : `编辑${label}`
})

const regionListItems = computed(() => {
  const slots = layout.value.slots_def || []
  return slots.map((slot, idx) => {
    if (isSecurity.value) {
      const type = (slot.groups?.[0]?.port_type || '1g') as PortType
      const count = slot.groups?.[0]?.count || 1
      const layoutMode = slot.zone_layout || 'auto'
      return {
        index: idx,
        title: slot.zone_label || `接口区 ${idx + 1}`,
        summary: [
          PORT_TYPE_LABELS[type],
          `${count} 口`,
          SECURITY_ZONE_LAYOUT_LABELS[layoutMode],
          `${Math.round(slot.layout_w ?? 80)}×${Math.round(slot.layout_h ?? 80)}`,
        ].join(' · '),
        active: selectedSecurityZoneIdx.value === idx,
      }
    }
    const kind = (slot.server_slot_kind || 'nic_10g') as ServerSlotKind
    const ori = (serverForm.form_factor === 1
      ? 'horizontal'
      : (slot.orientation || 'horizontal')) as ServerSlotOrientation
    const count = slot.groups?.[0]?.count || 0
    const portType = (slot.groups?.[0]?.port_type || serverSlotDefaultPortType(kind)) as PortType
    const size = resolveSlotSize(slot, serverForm.form_factor)
    return {
      index: idx,
      title: `扩展卡 ${idx + 1}`,
      summary: [
        SERVER_SLOT_KIND_LABELS[kind],
        SERVER_ORIENTATION_LABELS[ori],
        isPortlessServerSlot(kind) ? '无接口' : `${PORT_TYPE_LABELS[portType]} ×${count}`,
        `${Math.round(size.w)}×${Math.round(size.h)}`,
      ].join(' · '),
      active: selectedServerSlotIdx.value === idx,
    }
  })
})

function selectRegionItem(idx: number) {
  if (isServer.value) selectedServerSlotIdx.value = idx
  if (isSecurity.value) selectedSecurityZoneIdx.value = idx
}

/** 列表单击：可编辑时直接打开对话框，锁定时仅选中 */
function onRegionListItemClick(idx: number) {
  selectRegionItem(idx)
  if (layoutCanEdit.value) {
    openRegionEditor('edit', idx)
  }
}

function fillRegionFormFromSlot(slotIdx: number) {
  const slot = layout.value.slots_def?.[slotIdx]
  if (!slot) return
  if (isSecurity.value) {
    regionForm.zone_label = slot.zone_label || `接口区${slotIdx + 1}`
    regionForm.port_type = (slot.groups?.[0]?.port_type || '1g') as PortType
    regionForm.count = slot.groups?.[0]?.count || 1
    regionForm.zone_layout = (slot.zone_layout || 'auto') as SecurityZoneLayout
    regionForm.layout_w = Math.round(slot.layout_w ?? 80)
    regionForm.layout_h = Math.round(slot.layout_h ?? 80)
    return
  }
  const kind = (slot.server_slot_kind || 'nic_10g') as ServerSlotKind
  const size = resolveSlotSize(slot, serverForm.form_factor)
  regionForm.server_slot_kind = kind
  regionForm.orientation = (serverForm.form_factor === 1
    ? 'horizontal'
    : (slot.orientation || 'horizontal')) as ServerSlotOrientation
  regionForm.port_type = (slot.groups?.[0]?.port_type || serverSlotDefaultPortType(kind)) as PortType
  regionForm.layout_w = Math.round(size.w)
  regionForm.layout_h = Math.round(size.h)
  regionForm.count = isPortlessServerSlot(kind) ? 0 : (slot.groups?.[0]?.count || 2)
}

function openRegionEditor(mode: 'add' | 'edit', slotIdx?: number) {
  if (!layoutCanEdit.value) {
    ElMessage.warning('布局已锁定，请先点击「编辑布局」')
    return
  }
  regionEditorMode.value = mode
  if (mode === 'edit' && slotIdx !== undefined && slotIdx !== null) {
    const slot = layout.value.slots_def?.[slotIdx]
    if (!slot) {
      ElMessage.warning('未找到该扩展卡/接口区')
      return
    }
    regionEditorIndex.value = slotIdx
    selectRegionItem(slotIdx)
    fillRegionFormFromSlot(slotIdx)
  } else {
    regionEditorIndex.value = null
    if (isSecurity.value) {
      const n = (layout.value.slots_def?.length ?? 0) + 1
      regionForm.zone_label = `接口区${n}`
      regionForm.port_type = '1g'
      regionForm.count = 2
      regionForm.zone_layout = 'auto'
      regionForm.layout_w = 120
      regionForm.layout_h = 80
    } else {
      regionForm.server_slot_kind = 'nic_10g'
      regionForm.orientation = 'horizontal'
      regionForm.port_type = '10g'
      regionForm.count = 2
      try {
        const size = resolveSlotSize(
          {
            orientation: 'horizontal',
            groups: [],
            layout_w: null,
            layout_h: null,
          } as LayoutSlotDef,
          serverForm.form_factor,
        )
        regionForm.layout_w = Math.round(size.w)
        regionForm.layout_h = Math.round(size.h)
      } catch {
        regionForm.layout_w = 120
        regionForm.layout_h = 40
      }
    }
  }
  regionEditorVisible.value = true
}

function closeRegionEditor() {
  regionEditorVisible.value = false
}

function applyServerSlotFields(slotIdx: number, opts: { useGridDefaultSize?: boolean } = {}) {
  const slot = layout.value.slots_def?.[slotIdx]
  if (!slot) return
  const kind = regionForm.server_slot_kind
  slot.server_slot_kind = kind
  if (isPortlessServerSlot(kind)) {
    slot.groups = []
  } else {
    const count = normalizeServerSlotPortCount(regionForm.count || 1)
    const portType = regionForm.port_type || serverSlotDefaultPortType(kind)
    slot.groups = [{
      id: slot.groups?.[0]?.id || crypto.randomUUID().slice(0, 8),
      port_type: portType,
      count,
      layout_x: null,
      layout_y: null,
    }]
  }

  const nextOri: ServerSlotOrientation =
    serverForm.form_factor === 1 ? 'horizontal' : regionForm.orientation
  const prevOri = (slot.orientation || 'horizontal') as ServerSlotOrientation
  slot.orientation = nextOri

  if (opts.useGridDefaultSize) {
    // 新建：与默认扩展卡一致，交给布局引擎按网格赋尺寸
    slot.layout_w = null
    slot.layout_h = null
    slot.layout_x = null
    slot.layout_y = null
  } else if (prevOri !== nextOri) {
    // 改放置方向：清空尺寸与坐标，重新按网格/竖卡规则排布
    slot.layout_w = null
    slot.layout_h = null
    slot.layout_x = null
    slot.layout_y = null
    if (nextOri === 'vertical') {
      ;(layout.value.slots_def || []).forEach((s) => {
        if ((s.orientation || 'horizontal') === 'vertical') {
          s.layout_x = null
          s.layout_y = null
        }
      })
    }
  }
  // 编辑且方向未变：保留已有 layout_w/h（含用户拖拽缩放后的尺寸）

  ;(layout.value.ports || [])
    .filter((p) => p.slot_index === slotIdx + 1)
    .forEach((p) => { p.layout_locked = false })
}

function onRegionServerKindChange(kind: ServerSlotKind | string) {
  const next = kind as ServerSlotKind
  regionForm.server_slot_kind = next
  if (isPortlessServerSlot(next)) {
    regionForm.count = 0
    return
  }
  regionForm.port_type = serverSlotDefaultPortType(next)
  if (!regionForm.count || regionForm.count < 1) regionForm.count = 2
}

function onRegionPortCountChange(val: number | undefined) {
  if (val != null) regionForm.count = normalizeServerSlotPortCount(val)
}

function onSecurityZoneCountChange(val: number | undefined) {
  if (val == null) return
  regionForm.count = Math.max(1, Math.min(128, Math.round(val)))
  // 满 8 口自动切换为双行
  if (regionForm.count >= 8 && regionForm.zone_layout === 'single_row') {
    regionForm.zone_layout = 'two_row'
  }
}

function confirmRegionEditor() {
  if (!layoutCanEdit.value) {
    ElMessage.warning('布局已锁定，请先点击「编辑布局」')
    return
  }
  if (isSecurity.value) {
    if (regionEditorMode.value === 'add') {
      if ((layout.value.slots_def?.length ?? 0) >= 16) return
      if (!layout.value.slots_def) layout.value.slots_def = []
      const slot = newSecurityZoneSlot(
        regionForm.zone_label.trim() || `接口区${layout.value.slots_def.length + 1}`,
        regionForm.port_type,
        regionForm.count,
        regionForm.zone_layout,
      )
      slot.layout_w = regionForm.layout_w
      slot.layout_h = regionForm.layout_h
      layout.value.slots_def.push(slot)
      layout.value.slot_count = layout.value.slots_def.length
      const idx = layout.value.slots_def.length - 1
      syncPortsFromSlotsDef(layout.value, true)
      securityPanelView.value = layoutSecurityFrontPanel(layout.value)
      syncLegacyFromPortLayout(props.node)
      selectedSecurityZoneIdx.value = idx
    } else if (regionEditorIndex.value != null) {
      const idx = regionEditorIndex.value
      onSecurityZoneChange(idx, {
        label: regionForm.zone_label.trim(),
        port_type: regionForm.port_type,
        count: regionForm.count,
        zone_layout: regionForm.zone_layout,
        layout_w: regionForm.layout_w,
        layout_h: regionForm.layout_h,
      })
      selectedSecurityZoneIdx.value = idx
    }
  } else if (isServer.value) {
    if (regionEditorMode.value === 'add') {
      addServerSlot(
        layout.value,
        regionForm.server_slot_kind,
        isPortlessServerSlot(regionForm.server_slot_kind) ? 1 : Math.max(1, regionForm.count),
      )
      const idx = (layout.value.slots_def?.length ?? 1) - 1
      applyServerSlotFields(idx, { useGridDefaultSize: true })
      applyLayout()
      selectedServerSlotIdx.value = idx
    } else if (regionEditorIndex.value != null) {
      const idx = regionEditorIndex.value
      applyServerSlotFields(idx)
      applyLayout()
      selectedServerSlotIdx.value = idx
    }
  }
  closeRegionEditor()
}

function removeRegionItem(idx: number) {
  if (!layoutCanEdit.value) return
  if (isSecurity.value) {
    onRemoveSecurityZone(idx)
    if (selectedSecurityZoneIdx.value === idx) selectedSecurityZoneIdx.value = null
    else if (selectedSecurityZoneIdx.value != null && selectedSecurityZoneIdx.value > idx) {
      selectedSecurityZoneIdx.value -= 1
    }
    return
  }
  onRemoveSlot(idx)
  if (selectedServerSlotIdx.value === idx) selectedServerSlotIdx.value = null
  else if (selectedServerSlotIdx.value != null && selectedServerSlotIdx.value > idx) {
    selectedServerSlotIdx.value -= 1
  }
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
  // layout 中为上次已应用值；v-model 可能已写成中间非法值（如 5）
  const prev = layout.value.uplink_port_count ?? 4
  const next = normalizeGigabitUplinkCount(val, prev)
  switchForm.uplink_port_count = next
  if (!layoutCanEdit.value) return
  onSwitchFormChange()
}

function onTenGigabitUplinkChange(val: number | undefined) {
  if (val == null) return
  const prev = layout.value.uplink_port_count ?? 4
  const next = normalizeTenGigabitUplinkCount(val, prev)
  switchForm.uplink_port_count = next
  if (!layoutCanEdit.value) return
  onSwitchFormChange()
}

function openAddSlot() {
  if (isServer.value) {
    openRegionEditor('add')
    return
  }
  addForm.port_type = '1g'
  addForm.count = 2
  addSlotVisible.value = true
}

function confirmAddSlot() {
  if ((layout.value.slots_def?.length ?? 0) >= MAX_SLOT_COUNT) return
  addSlotWithGroup(layout.value, addForm.port_type, addForm.count)
  applyLayout()
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
  // 服务器：按 slots_def 重建端口并刷新面板，保证列表与图形同步
  applyLayout()
}

function openPeerDialog(port: FramePort) {
  if (!portsCanEdit.value) return
  selectedPortId.value = port.id
  selectedGroupId.value = port.group_id
  const useInventory = !!port.peer_device_id
  peerForm.source = useInventory ? 'inventory' : 'define'
  peerForm.peer_node_id = port.peer_node_id
  peerForm.peer_port = port.peer_port
  peerForm.peer_label = port.peer_label || ''
  peerForm.peer_device_id = port.peer_device_id || null
  peerForm.peer_device_name = port.peer_device_name || null
  peerVisible.value = true
  if (peerForm.source === 'inventory') void loadInventoryDevices()
}

function onPeerSourceChange(source: string | number | boolean | undefined) {
  const next: 'define' | 'inventory' = source === 'inventory' ? 'inventory' : 'define'
  peerForm.source = next
  peerForm.peer_port = null
  if (next === 'define') {
    peerForm.peer_device_id = null
    peerForm.peer_device_name = null
  } else {
    peerForm.peer_node_id = null
    void loadInventoryDevices()
  }
}

function onInventoryDeviceChange(deviceId: string | null) {
  peerForm.peer_device_id = deviceId
  peerForm.peer_port = null
  const device = inventoryDevices.value.find((d) => d.id === deviceId)
  peerForm.peer_device_name = device
    ? device.name || device.hostname
    : null
  // 若台账已绑定项目内定义节点，顺带记下 node id（保存时建 link）
  if (deviceId) {
    const bound = props.peerNodes.find((n) => n.device_id === deviceId)
    peerForm.peer_node_id = bound?.id || null
  } else {
    peerForm.peer_node_id = null
  }
}

function confirmPeer() {
  if (!selectedPort.value) return
  if (peerForm.source === 'inventory') {
    selectedPort.value.peer_device_id = peerForm.peer_device_id || null
    selectedPort.value.peer_device_name = peerForm.peer_device_name || null
    selectedPort.value.peer_port = peerForm.peer_port || null
    selectedPort.value.peer_label = peerForm.peer_label.trim() || null
    // 有绑定节点则写 peer_node_id，否则清空定义对端
    selectedPort.value.peer_node_id = peerForm.peer_node_id || null
  } else {
    selectedPort.value.peer_node_id = peerForm.peer_node_id || null
    selectedPort.value.peer_port = peerForm.peer_port || null
    selectedPort.value.peer_label = peerForm.peer_label.trim() || null
    selectedPort.value.peer_device_id = null
    selectedPort.value.peer_device_name = null
  }
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
  selectedPort.value.peer_device_id = null
  selectedPort.value.peer_device_name = null
  peerForm.peer_node_id = null
  peerForm.peer_port = null
  peerForm.peer_label = ''
  peerForm.peer_device_id = null
  peerForm.peer_device_name = null
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

function portHitPad(port: FramePort) {
  const pad = Math.max(5, Math.min(9, Math.round(Math.min(port.w, port.h) * 0.35)))
  const tabExtra =
    !port.port_type || port.port_type === '1g' || port.port_type === 'bmc' || port.port_type === 'other'
      ? Math.max(2.5, port.h * 0.26)
      : 0
  return {
    x: port.x - pad,
    y: port.y - pad - tabExtra,
    w: port.w + pad * 2,
    h: port.h + pad * 2 + tabExtra + 4,
  }
}

function portJackPath(port: FramePort): string {
  const { x, y, w, h } = port
  if (port.port_type === '40_100g') {
    const r = Math.min(2.2, w * 0.1)
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
    const inset = Math.max(1.8, Math.min(3.2, w * 0.14))
    const r = Math.min(1.8, w * 0.1)
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
  // RJ45：上方钥匙扣 + 圆角壳体，比例更接近真实网口
  const tabW = Math.min(w * 0.58, w - 2.5)
  const tabH = Math.max(2.2, Math.min(4.5, h * 0.26))
  const tabX = x + (w - tabW) / 2
  const r = Math.min(2.2, w * 0.14)
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

function serverPortCavity(port: FramePort) {
  const insetX = Math.max(2, port.w * 0.16)
  const insetTop = Math.max(2.2, port.h * 0.22)
  const insetBot = Math.max(2, port.h * 0.18)
  return {
    x: port.x + insetX,
    y: port.y + insetTop,
    w: Math.max(4, port.w - insetX * 2),
    h: Math.max(3, port.h - insetTop - insetBot),
  }
}

function serverPortNumFontSize(port: FramePort) {
  return Math.max(7, Math.min(11, Math.round(Math.min(port.w, port.h) * 0.48)))
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

function onSecurityZoneMouseDown(
  event: MouseEvent,
  zone: NonNullable<typeof securityPanelView.value>['zones'][0],
) {
  if (!layoutCanEdit.value || !isSecurity.value) return
  event.stopPropagation()
  selectedPortId.value = null
  selectedGroupId.value = null
  selectedSecurityZoneIdx.value = zone.slotIndex - 1
  const cursor = svgPoint(event)
  if (!cursor) return
  const frameX = cursor.x - svgOffset.value
  const frameY = cursor.y - 14
  draggingSlot.value = {
    slotIndex: zone.slotIndex - 1,
    offsetX: frameX - zone.x,
    offsetY: frameY - zone.y,
  }
}

function onSecurityZoneResizeMouseDown(
  event: MouseEvent,
  zone: NonNullable<typeof securityPanelView.value>['zones'][0],
) {
  if (!layoutCanEdit.value || !isSecurity.value) return
  event.stopPropagation()
  selectedSecurityZoneIdx.value = zone.slotIndex - 1
  const cursor = svgPoint(event)
  if (!cursor) return
  resizingServerSlot.value = {
    slotIndex: zone.slotIndex - 1,
    startX: cursor.x - svgOffset.value,
    startY: cursor.y - 14,
    originW: zone.w,
    originH: zone.h,
  }
}

function onSecurityPortMouseDown(event: MouseEvent, port: FramePort) {
  if (!layoutCanEdit.value || !isSecurity.value || port.slot_index == null) return
  const zone = securityPanelView.value?.zones.find((z) => z.slotIndex === port.slot_index)
  if (!zone) return
  onSecurityZoneMouseDown(event, zone)
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

/** 参考图横置 Slot 内平行散热线（稀疏绘制，降低 SVG 节点数） */
function serverSlotHatchLines(slot: NonNullable<typeof serverPanelView.value>['slots'][0]) {
  const marks: Array<{ x1: number; y1: number; x2: number; y2: number }> = []
  const pad = 6
  const step = Math.max(7, slot.h / 4)
  const top = slot.y + pad
  const bottom = slot.y + slot.h - pad
  for (let y = top; y <= bottom + 0.1; y += step) {
    marks.push({
      x1: slot.x + pad,
      y1: y,
      x2: slot.x + slot.w - pad,
      y2: y,
    })
  }
  return marks
}

/** 拖拽/缩放时只更新当前卡视觉坐标，避免整板重算 */
function patchServerSlotVisual(slotIndex: number) {
  const view = serverPanelView.value
  const slot = layout.value.slots_def?.[slotIndex]
  if (!view || !slot) return
  const visual = view.slots.find((s) => s.slotIndex === slotIndex + 1)
  if (!visual) return
  if (slot.layout_x != null) visual.x = slot.layout_x
  if (slot.layout_y != null) visual.y = slot.layout_y
  if (slot.layout_w != null) visual.w = slot.layout_w
  if (slot.layout_h != null) visual.h = slot.layout_h
  if (slot.server_slot_kind) {
    visual.kind = slot.server_slot_kind
    visual.label = SERVER_SLOT_KIND_LABELS[slot.server_slot_kind]
    visual.shortLabel = shortKindLabel(slot.server_slot_kind)
  }
}

function shortKindLabel(kind: ServerSlotKind): string {
  if (kind === 'nic_1g') return '1G'
  if (kind === 'nic_10g') return '10G'
  if (kind === 'hba') return 'HBA'
  if (kind === 'raid') return 'RAID'
  return 'BLANK'
}

function serverPsuFanPath(psu: { x: number; y: number; w: number; h: number }) {
  const cx = psu.x + psu.w * 0.32
  const cy = psu.y + psu.h * 0.5
  const r = Math.min(psu.w, psu.h) * 0.28
  return { cx, cy, r }
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

  if (resizingServerSlot.value && isSecurity.value) {
    const dx = frameX - resizingServerSlot.value.startX
    const dy = frameY - resizingServerSlot.value.startY
    resizeSecurityZoneInPanel(
      layout.value,
      resizingServerSlot.value.slotIndex,
      resizingServerSlot.value.originW + dx,
      resizingServerSlot.value.originH + dy,
    )
    securityPanelView.value = layoutSecurityFrontPanel(layout.value)
    return
  }

  if (resizingServerSlot.value) {
    const dx = frameX - resizingServerSlot.value.startX
    const dy = frameY - resizingServerSlot.value.startY
    resizeServerSlotInPanel(
      layout.value,
      resizingServerSlot.value.slotIndex,
      resizingServerSlot.value.originW + dx,
      resizingServerSlot.value.originH + dy,
    )
    patchServerSlotVisual(resizingServerSlot.value.slotIndex)
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

  if (draggingSlot.value && isSecurity.value) {
    moveSecurityZoneInPanel(
      layout.value,
      draggingSlot.value.slotIndex,
      frameX - draggingSlot.value.offsetX,
      frameY - draggingSlot.value.offsetY,
    )
    securityPanelView.value = layoutSecurityFrontPanel(layout.value)
    return
  }

  if (draggingSlot.value && isServer.value) {
    moveServerSlotInPanel(
      layout.value,
      draggingSlot.value.slotIndex,
      frameX - draggingSlot.value.offsetX,
      frameY - draggingSlot.value.offsetY,
    )
    patchServerSlotVisual(draggingSlot.value.slotIndex)
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
  const wasServerDrag =
    !!resizingServerSlot.value
    || !!draggingServerPort.value
    || (!!draggingSlot.value && isServer.value)
  if (
    resizingServerSlot.value
    || draggingServerPort.value
    || (draggingSlot.value && (isServer.value || isSecurity.value))
  ) {
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
  // 拖拽结束后做一次完整重算，校正端口位置
  if (wasServerDrag) refreshServerPanel()
}

watch(
  () => props.node.id,
  () => {
    displayScale.value = frameDisplayScalePercent(layout.value)
    syncSwitchFormFromLayout()
    syncServerFormFromLayout()
    refreshSwitchPanel()
    refreshServerPanel()
    refreshSecurityPanel()
    viewZoom.value = defaultViewZoomForKind()
  },
)

watch(layoutCanEdit, (can) => {
  if (!can) regionEditorVisible.value = false
})

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
    if (peerForm.source !== 'define') return
    if (peerForm.peer_port && !peerPortOptions.value.some((p) => p.id === peerForm.peer_port)) {
      peerForm.peer_port = null
    }
  },
)

watch(
  () => peerForm.peer_device_id,
  () => {
    if (peerForm.source !== 'inventory') return
    if (peerForm.peer_port && !peerPortOptions.value.some((p) => p.id === peerForm.peer_port)) {
      peerForm.peer_port = null
    }
  },
)

syncSwitchFormFromLayout()
syncServerFormFromLayout()
refreshSwitchPanel()
refreshServerPanel()
refreshSecurityPanel()

defineExpose({
  openPeerDialog,
  openPortEdit,
  onPortClick,
})
</script>

<template>
  <div class="frame-editor" @mousemove="onMouseMove" @mouseup="onMouseUp" @mouseleave="onMouseUp">
    <div v-if="layoutCanEdit || isServer || isSecurity" class="config-panel">
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

          <template v-if="isGigabitSwitch || isTenGigabitSwitch || isAggregationSwitch">
            <label>板卡数</label>
            <el-input-number
              v-model="switchForm.optical_card_count"
              :min="1"
              :max="16"
              size="small"
              @change="onAccessSwitchCardChange"
            />
            <label>{{ isGigabitSwitch ? '电口个数' : '光口个数' }}</label>
            <el-input-number
              v-model="switchForm.optical_ports_per_card"
              :min="1"
              :max="128"
              size="small"
              @change="onAccessSwitchCardChange"
            />
            <span class="field-hint">
              总{{ isGigabitSwitch ? '电口' : '光口' }} {{ switchForm.main_port_count }}（板卡数 ×
              {{ isGigabitSwitch ? '电口' : '光口' }}个数）
            </span>
            <label>{{ isGigabitSwitch ? '上联光口' : '40/100G上联' }}</label>
            <el-input-number
              v-model="switchForm.uplink_port_count"
              :min="0"
              :max="8"
              :step="isGigabitSwitch ? 1 : 2"
              size="small"
              @change="isGigabitSwitch ? onGigabitUplinkChange : onTenGigabitUplinkChange"
            />
            <span class="field-hint">
              <template v-if="isGigabitSwitch">≤8；&gt;4 为 6/8（点加号 4→6）</template>
              <template v-else-if="isAggregationSwitch">汇聚：10G下联接入，40/100G上联核心</template>
              <template v-else>≤8，须为偶数，两排向后扩展</template>
            </span>
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
            <el-select v-model="card.card_type" size="small" style="width: 120px" @change="onEditorLineCardTypeChange(card)">
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
              :min="card.card_type === 'blank' ? 0 : 1"
              :max="128"
              size="small"
              :disabled="card.card_type === 'blank'"
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
            :disabled="!layoutCanEdit"
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
              :disabled="!layoutCanEdit"
              @change="onServerOnboard1gChange"
            />
            <el-button
              v-if="layoutCanEdit"
              type="primary"
              size="small"
              @click.stop.prevent="openRegionEditor('add')"
            >
              + 添加扩展卡
            </el-button>
          </template>
        </div>

        <div v-if="serverPanelSide === 'rear'" class="region-list">
          <div
            v-for="item in regionListItems"
            :key="item.index"
            class="region-list-item"
            :class="{ active: item.active }"
            @click="onRegionListItemClick(item.index)"
          >
            <div class="region-list-main">
              <div class="region-list-title">{{ item.title }}</div>
              <div class="region-list-summary">{{ item.summary }}</div>
            </div>
            <div v-if="layoutCanEdit" class="region-list-actions" @click.stop>
              <el-button
                size="small"
                link
                type="primary"
                @click.stop.prevent="openRegionEditor('edit', item.index)"
              >
                编辑
              </el-button>
              <el-button
                v-if="regionListItems.length > 1"
                size="small"
                link
                type="danger"
                @click.stop.prevent="removeRegionItem(item.index)"
              >
                删除
              </el-button>
            </div>
          </div>
          <el-empty v-if="!regionListItems.length" description="暂无扩展卡" :image-size="48" />
          <p v-if="layoutCanEdit && regionListItems.length" class="drag-hint">
            单击列表项或「编辑」打开对话框；面板上可拖动扩展卡，选中后点蓝色「编辑」角标也可编辑
          </p>
          <p v-else-if="!layoutCanEdit && regionListItems.length" class="drag-hint">
            布局已锁定，不可添加/编辑扩展卡；点击「编辑布局」后可修改
          </p>
        </div>
      </template>

      <template v-else-if="isSecurity">
        <div class="config-row">
          <label>设备高度 (U)</label>
          <el-button-group>
            <el-button
              size="small"
              :type="normalizeSecurityHeightU(layout.height_u) === 1 ? 'primary' : 'default'"
              :disabled="!layoutCanEdit"
              @click="onSecurityHeightChange(1)"
            >
              1U
            </el-button>
            <el-button
              size="small"
              :type="normalizeSecurityHeightU(layout.height_u) === 2 ? 'primary' : 'default'"
              :disabled="!layoutCanEdit"
              @click="onSecurityHeightChange(2)"
            >
              2U
            </el-button>
          </el-button-group>
          <span class="frame-size">
            {{ normalizeSecurityHeightU(layout.height_u) }}U ·
            {{ Math.round(layout.frame_width) }}×{{ Math.round(layout.frame_height) }}px
          </span>
          <el-button
            v-if="layoutCanEdit"
            type="primary"
            size="small"
            :disabled="(layout.slots_def?.length ?? 0) >= 16"
            @click.stop.prevent="openRegionEditor('add')"
          >
            + 添加接口区
          </el-button>
          <el-button v-if="layoutCanEdit" size="small" @click="onResetSecurityZoneLayout">自动排列</el-button>
        </div>
        <div class="region-list">
          <div
            v-for="item in regionListItems"
            :key="item.index"
            class="region-list-item"
            :class="{ active: item.active }"
            @click="onRegionListItemClick(item.index)"
          >
            <div class="region-list-main">
              <div class="region-list-title">{{ item.title }}</div>
              <div class="region-list-summary">{{ item.summary }}</div>
            </div>
            <div v-if="layoutCanEdit" class="region-list-actions" @click.stop>
              <el-button
                size="small"
                link
                type="primary"
                @click.stop.prevent="openRegionEditor('edit', item.index)"
              >
                编辑
              </el-button>
              <el-button
                v-if="regionListItems.length > 1"
                size="small"
                link
                type="danger"
                @click.stop.prevent="removeRegionItem(item.index)"
              >
                删除
              </el-button>
            </div>
          </div>
          <el-empty v-if="!regionListItems.length" description="暂无接口区" :image-size="48" />
          <p v-if="layoutCanEdit && regionListItems.length" class="drag-hint">
            单击列表项或「编辑」打开对话框；面板上可拖动接口区移动/缩放
          </p>
          <p v-else-if="!layoutCanEdit && regionListItems.length" class="drag-hint">
            布局已锁定，不可添加/编辑接口区；点击「编辑布局」后可修改
          </p>
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
      <el-button v-if="layoutCanEdit && !isSwitch && !isServer && !isSecurity" size="small" @click="applyLayout">自动适配设备框架</el-button>
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
              :class="[zone.kind, { blank: zone.blank }]"
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
            <text
              v-if="zone.kind === 'card' && zone.blank"
              :x="zone.x + zone.w / 2"
              :y="zone.y + zone.h / 2 + 4"
              text-anchor="middle"
              class="blank-card-mark"
            >
              BLANK
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
            :class="{ selected: selectedPortId === port.id, linked: !!(port.peer_node_id || port.peer_device_id) }"
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
            <stop offset="0%" stop-color="#f4f6f8" />
            <stop offset="100%" stop-color="#d8dee6" />
          </linearGradient>
          <linearGradient id="serverFrontEar" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#b8bfc9" />
            <stop offset="50%" stop-color="#e8ebf0" />
            <stop offset="100%" stop-color="#a8b0bc" />
          </linearGradient>
          <pattern id="ventMesh" width="6" height="6" patternUnits="userSpaceOnUse">
            <path d="M0 3 H6 M3 0 V6" stroke="#b0b8c4" stroke-width="0.5" />
          </pattern>
        </defs>
        <rect :x="0" y="14" :width="svgOffset - 2" :height="layout.frame_height" rx="2" fill="url(#serverFrontEar)" stroke="#8a929e" />
        <circle :cx="svgOffset / 2 - 1" :cy="28" r="2.5" fill="none" stroke="#606266" />
        <circle :cx="svgOffset / 2 - 1" :cy="14 + layout.frame_height - 14" r="2.5" fill="none" stroke="#606266" />
        <rect :x="layout.frame_width + svgOffset + 2" y="14" :width="svgOffset - 2" :height="layout.frame_height" rx="2" fill="url(#serverFrontEar)" stroke="#8a929e" />
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
            fill="url(#serverFrontChassis)"
            stroke="#4a5562"
            stroke-width="1.5"
          />
          <text :x="12" y="16" class="panel-brand">{{ node.name }}</text>
          <text :x="layout.frame_width - 12" y="16" text-anchor="end" class="panel-model">
            前面板 · {{ serverFrontPanelView.title }}
          </text>
          <!-- Left I/O bezel（与交换机 MGMT 区同风格） -->
          <rect
            x="8"
            y="24"
            :width="serverFrontPanelView.formFactor === 1 ? 64 : 80"
            :height="layout.frame_height - 32"
            rx="2"
            class="panel-zone"
          />
          <text x="16" y="40" class="panel-brand">DCIM</text>
          <text x="16" y="52" class="panel-model">Server</text>
          <circle :cx="22" :cy="66" r="5" fill="#ecf5ff" stroke="#409eff" />
          <rect x="14" y="78" width="4" height="4" rx="1" fill="#67c23a" />
          <rect x="22" y="78" width="4" height="4" rx="1" fill="#409eff" />
          <rect x="30" y="78" width="4" height="4" rx="1" fill="#e6a23c" />
          <rect
            v-if="serverFrontPanelView.formFactor !== 1"
            x="16"
            y="90"
            width="10"
            height="6"
            rx="1"
            fill="#ecf5ff"
            stroke="#409eff"
          />
          <rect
            v-if="serverFrontPanelView.formFactor !== 1"
            x="28"
            y="90"
            width="10"
            height="6"
            rx="1"
            fill="#f0f9eb"
            stroke="#67c23a"
          />
          <!-- Side vents -->
          <rect :x="layout.frame_width - 28" y="24" width="20" :height="layout.frame_height - 32" fill="url(#ventMesh)" opacity="0.55" />
          <!-- Drive bays -->
          <g v-for="bay in serverFrontPanelView.driveBays" :key="`${bay.row}-${bay.col}`">
            <rect :x="bay.x" :y="bay.y" :width="bay.w" :height="bay.h" rx="2" class="panel-zone card" />
            <rect :x="bay.x + 3" :y="bay.y + bay.h - 8" :width="bay.w - 6" height="4" rx="1" fill="#e4e7ed" stroke="#c0c4cc" />
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
            <stop offset="0%" stop-color="#f4f6f8" />
            <stop offset="100%" stop-color="#d8dee6" />
          </linearGradient>
          <linearGradient id="serverEar" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#b8bfc9" />
            <stop offset="50%" stop-color="#e8ebf0" />
            <stop offset="100%" stop-color="#a8b0bc" />
          </linearGradient>
          <pattern id="rearVentHex" width="8" height="8" patternUnits="userSpaceOnUse">
            <path d="M4 1 L7 4 L4 7 L1 4 Z" fill="none" stroke="#b0b8c4" stroke-width="0.6" />
          </pattern>
        </defs>
        <rect :x="0" y="14" :width="svgOffset - 2" :height="layout.frame_height" rx="2" fill="url(#serverEar)" stroke="#8a929e" />
        <circle :cx="svgOffset / 2 - 1" :cy="28" r="2.5" fill="none" stroke="#606266" />
        <circle :cx="svgOffset / 2 - 1" :cy="14 + layout.frame_height - 14" r="2.5" fill="none" stroke="#606266" />
        <rect :x="layout.frame_width + svgOffset + 2" y="14" :width="svgOffset - 2" :height="layout.frame_height" rx="2" fill="url(#serverEar)" stroke="#8a929e" />
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
            fill="url(#serverChassis)"
            stroke="#4a5562"
            stroke-width="1.5"
          />
          <text :x="12" y="14" class="panel-brand">{{ node.name }}</text>
          <text :x="layout.frame_width - 12" y="14" text-anchor="end" class="panel-model">
            后面板 · {{ serverPanelView.title }} · Slot {{ serverPanelView.slots.length }}
          </text>

          <!-- OCP -->
          <rect
            :x="serverPanelView.ioRegions.ocp.x"
            :y="serverPanelView.ioRegions.ocp.y"
            :width="serverPanelView.ioRegions.ocp.w"
            :height="serverPanelView.ioRegions.ocp.h"
            rx="2"
            class="panel-zone"
          />
          <text
            :x="serverPanelView.ioRegions.ocp.x + 8"
            :y="serverPanelView.ioRegions.ocp.y + 12"
            class="zone-label"
          >
            OCP
          </text>

          <!-- Mid fixed I/O band -->
          <rect
            :x="serverPanelView.fixedIo.x"
            :y="serverPanelView.fixedIo.y"
            :width="serverPanelView.fixedIo.w"
            :height="serverPanelView.fixedIo.h"
            rx="2"
            class="panel-zone"
          />
          <!-- VGA -->
          <rect
            :x="serverPanelView.ioRegions.vga.x"
            :y="serverPanelView.ioRegions.vga.y"
            :width="serverPanelView.ioRegions.vga.w"
            :height="serverPanelView.ioRegions.vga.h"
            rx="1"
            fill="#fafafa"
            stroke="#606266"
          />
          <text
            :x="serverPanelView.ioRegions.vga.x + serverPanelView.ioRegions.vga.w / 2"
            :y="serverPanelView.ioRegions.vga.y + serverPanelView.ioRegions.vga.h + 10"
            text-anchor="middle"
            class="mgmt-label"
          >
            VGA
          </text>
          <!-- Mgmt -->
          <rect
            :x="serverPanelView.ioRegions.mgmt.x"
            :y="serverPanelView.ioRegions.mgmt.y"
            :width="serverPanelView.ioRegions.mgmt.w"
            :height="serverPanelView.ioRegions.mgmt.h"
            rx="1"
            fill="#f0f9eb"
            stroke="#67c23a"
          />
          <text
            :x="serverPanelView.ioRegions.mgmt.x + serverPanelView.ioRegions.mgmt.w / 2"
            :y="serverPanelView.ioRegions.mgmt.y + serverPanelView.ioRegions.mgmt.h + 10"
            text-anchor="middle"
            class="mgmt-label"
          >
            Mgmt
          </text>
          <!-- USB stacked -->
          <rect
            :x="serverPanelView.ioRegions.usb.x"
            :y="serverPanelView.ioRegions.usb.y"
            :width="serverPanelView.ioRegions.usb.w"
            :height="serverPanelView.ioRegions.usb.h * 0.42"
            rx="1"
            fill="#ecf5ff"
            stroke="#909399"
          />
          <rect
            :x="serverPanelView.ioRegions.usb.x"
            :y="serverPanelView.ioRegions.usb.y + serverPanelView.ioRegions.usb.h * 0.55"
            :width="serverPanelView.ioRegions.usb.w"
            :height="serverPanelView.ioRegions.usb.h * 0.42"
            rx="1"
            fill="#ecf5ff"
            stroke="#909399"
          />
          <text
            :x="serverPanelView.ioRegions.usb.x + serverPanelView.ioRegions.usb.w / 2"
            :y="serverPanelView.ioRegions.usb.y + serverPanelView.ioRegions.usb.h + 10"
            text-anchor="middle"
            class="mgmt-label"
          >
            USB
          </text>

          <!-- PSU with fan + inlet -->
          <g v-for="psu in serverPanelView.psus" :key="psu.id">
            <rect :x="psu.x" :y="psu.y" :width="psu.w" :height="psu.h" rx="2" class="panel-zone psu-block" />
            <circle
              :cx="serverPsuFanPath(psu).cx"
              :cy="serverPsuFanPath(psu).cy"
              :r="serverPsuFanPath(psu).r"
              fill="none"
              stroke="#606266"
              stroke-width="1.2"
            />
            <line
              :x1="serverPsuFanPath(psu).cx - serverPsuFanPath(psu).r * 0.7"
              :y1="serverPsuFanPath(psu).cy - serverPsuFanPath(psu).r * 0.7"
              :x2="serverPsuFanPath(psu).cx + serverPsuFanPath(psu).r * 0.7"
              :y2="serverPsuFanPath(psu).cy + serverPsuFanPath(psu).r * 0.7"
              stroke="#909399"
              stroke-width="1"
            />
            <line
              :x1="serverPsuFanPath(psu).cx + serverPsuFanPath(psu).r * 0.7"
              :y1="serverPsuFanPath(psu).cy - serverPsuFanPath(psu).r * 0.7"
              :x2="serverPsuFanPath(psu).cx - serverPsuFanPath(psu).r * 0.7"
              :y2="serverPsuFanPath(psu).cy + serverPsuFanPath(psu).r * 0.7"
              stroke="#909399"
              stroke-width="1"
            />
            <rect
              :x="psu.x + psu.w * 0.58"
              :y="psu.y + psu.h * 0.28"
              :width="psu.w * 0.28"
              :height="psu.h * 0.44"
              rx="1"
              fill="#fafafa"
              stroke="#606266"
            />
            <text :x="psu.x + 6" :y="psu.y + 12" class="mgmt-label">{{ psu.label }}</text>
          </g>

          <!-- Expansion slots（参考图横置挡板风格） -->
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
            @dblclick.stop="layoutCanEdit && openRegionEditor('edit', slot.slotIndex - 1)"
          >
            <rect
              :x="slot.x"
              :y="slot.y"
              :width="slot.w"
              :height="slot.h"
              rx="1"
              fill="#fff"
              stroke="#303133"
              stroke-width="1.4"
            />
            <rect
              :x="slot.x + 2"
              :y="slot.y + 2"
              :width="slot.w - 4"
              :height="slot.h - 4"
              rx="0.5"
              :fill="serverCardPalette(slot.kind).face"
              :stroke="serverCardPalette(slot.kind).accent"
              stroke-width="0.8"
              opacity="0.95"
            />
            <line
              v-for="(m, mi) in serverSlotHatchLines(slot)"
              :key="mi"
              :x1="m.x1"
              :y1="m.y1"
              :x2="m.x2"
              :y2="m.y2"
              stroke="rgba(48,49,51,0.22)"
              stroke-width="0.8"
            />
            <text
              :x="slot.x + slot.w / 2"
              :y="slot.y + slot.h / 2 + 4"
              text-anchor="middle"
              class="slot-ref-label"
            >
              Slot{{ slot.slotIndex }}
            </text>
            <text
              v-if="slot.kind !== 'blank'"
              :x="slot.x + 8"
              :y="slot.y + 12"
              class="mgmt-label"
            >
              {{ slot.shortLabel }}
            </text>
            <rect
              v-if="selectedServerSlotIdx === slot.slotIndex - 1"
              :x="slot.x - 1"
              :y="slot.y - 1"
              :width="slot.w + 2"
              :height="slot.h + 2"
              rx="1.5"
              fill="none"
              stroke="#409eff"
              stroke-width="1.2"
              stroke-dasharray="3 2"
            />
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
            </g>
          </g>

          <!-- Ports -->
          <g
            v-for="port in layout.ports"
            :key="port.id"
            class="port port-interactive server-port"
            :class="{ selected: selectedPortId === port.id, linked: !!(port.peer_node_id || port.peer_device_id), locked: port.layout_locked }"
            @mousedown="onServerPortMouseDown($event, port)"
            @click.stop="onPortClick(port)"
            @dblclick.stop="openPeerDialog(port)"
          >
            <title>
              {{ port.label }} · {{ PORT_TYPE_LABELS[port.port_type || '1g'] }} · 单击选中，双击配置对端
            </title>
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
              stroke-width="1.35"
              class="port-face"
            />
            <rect
              v-if="port.port_type !== '10g'"
              :x="serverPortCavity(port).x"
              :y="serverPortCavity(port).y"
              :width="serverPortCavity(port).w"
              :height="serverPortCavity(port).h"
              rx="1"
              class="server-port-cavity"
              :style="{ stroke: portColors(port).stroke }"
            />
            <g
              v-if="(!port.port_type || port.port_type === '1g') && port.w >= 18 && port.h >= 12"
              class="server-port-pins"
              pointer-events="none"
            >
              <line
                v-for="n in 6"
                :key="n"
                :x1="serverPortCavity(port).x + (serverPortCavity(port).w * n) / 7"
                :y1="serverPortCavity(port).y + 1"
                :x2="serverPortCavity(port).x + (serverPortCavity(port).w * n) / 7"
                :y2="serverPortCavity(port).y + serverPortCavity(port).h - 1"
                stroke="rgba(212, 175, 55, 0.75)"
                stroke-width="0.7"
              />
            </g>
            <text
              :x="port.x + port.w / 2"
              :y="
                port.y +
                port.h / 2 +
                serverPortNumFontSize(port) * 0.35 -
                (port.h >= 14 && port.w >= 16 ? 1.2 : 0)
              "
              text-anchor="middle"
              class="server-port-num"
              :style="{ fontSize: `${serverPortNumFontSize(port)}px` }"
            >
              {{ port.label }}
            </text>
            <text
              v-if="port.h >= 14 && port.w >= 16"
              :x="port.x + port.w / 2"
              :y="port.y + port.h - 1.5"
              text-anchor="middle"
              class="server-port-type"
            >
              {{ PORT_TYPE_SHORT[port.port_type || '1g'] }}
            </text>
            <circle
              v-if="port.peer_node_id"
              :cx="port.x + port.w - 2"
              :cy="port.y + 2"
              r="2.6"
              fill="#67c23a"
              stroke="#fff"
              stroke-width="0.6"
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

          <!-- 扩展卡「编辑」角标置于端口之上，避免被接口热区挡住 -->
          <g
            v-for="slot in serverPanelView.slots"
            :key="`edit-badge-${slot.slotIndex}`"
          >
            <g
              v-if="layoutCanEdit && selectedServerSlotIdx === slot.slotIndex - 1"
              class="slot-edit-badge"
              @mousedown.stop
              @click.stop="openRegionEditor('edit', slot.slotIndex - 1)"
            >
              <rect
                :x="slot.x + slot.w - 36"
                :y="slot.y + 2"
                width="34"
                height="14"
                rx="2"
                fill="#409eff"
              />
              <text
                :x="slot.x + slot.w - 19"
                :y="slot.y + 12"
                text-anchor="middle"
                class="slot-edit-badge-text"
              >
                编辑
              </text>
            </g>
          </g>
        </g>
      </svg>

      <!-- Security front panel -->
      <svg
        v-else-if="isSecurity && securityPanelView"
        :key="`sec-panel-${normalizeSecurityHeightU(layout.height_u)}-${Math.round(layout.frame_height)}`"
        ref="svgRef"
        class="device-svg panel-svg security-panel"
        :width="svgDisplayWidth"
        :height="svgDisplayHeight"
        :viewBox="svgViewBox"
      >
        <defs>
          <linearGradient id="secChassis" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#f4f6f8" />
            <stop offset="100%" stop-color="#d8dee6" />
          </linearGradient>
          <linearGradient id="secEar" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#b8bfc9" />
            <stop offset="50%" stop-color="#e8ebf0" />
            <stop offset="100%" stop-color="#a8b0bc" />
          </linearGradient>
        </defs>

        <rect x="0" y="14" :width="svgOffset - 2" :height="layout.frame_height" rx="2" fill="url(#secEar)" stroke="#8a929e" />
        <circle :cx="svgOffset / 2 - 1" :cy="28" r="2.5" fill="none" stroke="#606266" />
        <circle :cx="svgOffset / 2 - 1" :cy="14 + layout.frame_height - 14" r="2.5" fill="none" stroke="#606266" />
        <rect
          :x="layout.frame_width + svgOffset + 2"
          y="14"
          :width="svgOffset - 2"
          :height="layout.frame_height"
          rx="2"
          fill="url(#secEar)"
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
            fill="url(#secChassis)"
            stroke="#4a5562"
            stroke-width="1.5"
          />
          <text :x="12" y="15" class="panel-brand">{{ node.name }}</text>
          <text :x="layout.frame_width - 12" y="15" text-anchor="end" class="panel-model">
            {{ normalizeSecurityHeightU(layout.height_u) }}U 安全设备 · {{ securityPanelView.title }}
          </text>

          <!-- Status / console block（对齐交换机 MGMT 区） -->
          <rect
            :x="securityPanelView.statusBlock.x"
            :y="securityPanelView.statusBlock.y"
            :width="securityPanelView.statusBlock.w"
            :height="securityPanelView.statusBlock.h"
            rx="2"
            class="panel-zone"
          />
          <text
            :x="securityPanelView.statusBlock.x + 8"
            :y="securityPanelView.statusBlock.y + 16"
            class="panel-brand"
          >
            DCIM
          </text>
          <text
            :x="securityPanelView.statusBlock.x + 8"
            :y="securityPanelView.statusBlock.y + 30"
            class="panel-model"
          >
            Security
          </text>
          <circle
            :cx="securityPanelView.statusBlock.x + 14"
            :cy="securityPanelView.statusBlock.y + 44"
            r="3.5"
            fill="#67c23a"
            stroke="#fff"
            stroke-width="0.8"
          />
          <circle
            :cx="securityPanelView.statusBlock.x + 28"
            :cy="securityPanelView.statusBlock.y + 44"
            r="3.5"
            fill="#e6a23c"
            stroke="#fff"
            stroke-width="0.8"
          />
          <circle
            :cx="securityPanelView.statusBlock.x + 42"
            :cy="securityPanelView.statusBlock.y + 44"
            r="3.5"
            fill="#c0c4cc"
            stroke="#909399"
            stroke-width="0.8"
          />
          <rect
            :x="securityPanelView.statusBlock.x + 8"
            :y="securityPanelView.statusBlock.y + securityPanelView.statusBlock.h - 28"
            width="14"
            height="12"
            rx="1"
            fill="#ecf5ff"
            stroke="#409eff"
          />
          <text
            :x="securityPanelView.statusBlock.x + 26"
            :y="securityPanelView.statusBlock.y + securityPanelView.statusBlock.h - 19"
            class="mgmt-label"
          >
            CONSOLE
          </text>
          <circle
            :cx="securityPanelView.statusBlock.x + 16"
            :cy="securityPanelView.statusBlock.y + securityPanelView.statusBlock.h - 8"
            r="3"
            fill="#c0c4cc"
            stroke="#909399"
          />
          <text
            :x="securityPanelView.statusBlock.x + 26"
            :y="securityPanelView.statusBlock.y + securityPanelView.statusBlock.h - 5"
            class="mgmt-label"
          >
            RESET
          </text>

          <g
            v-for="zone in securityPanelView.zones"
            :key="zone.id"
            class="sec-zone"
            :class="{
              dragging: draggingSlot?.slotIndex === zone.slotIndex - 1,
              selected: selectedSecurityZoneIdx === zone.slotIndex - 1,
            }"
            @mousedown="onSecurityZoneMouseDown($event, zone)"
            @dblclick.stop="layoutCanEdit && openRegionEditor('edit', zone.slotIndex - 1)"
          >
            <rect
              :x="zone.x"
              :y="zone.y"
              :width="zone.w"
              :height="zone.h"
              rx="2"
              class="panel-zone"
              :class="zone.portType === '10g' || zone.portType === '40_100g' ? 'uplink' : 'main'"
            />
            <text :x="zone.x + 6" :y="zone.y + 12" class="zone-label">{{ zone.label }}</text>
            <rect
              v-if="selectedSecurityZoneIdx === zone.slotIndex - 1"
              :x="zone.x - 1"
              :y="zone.y - 1"
              :width="zone.w + 2"
              :height="zone.h + 2"
              rx="2.5"
              fill="none"
              stroke="#409eff"
              stroke-width="1.2"
              stroke-dasharray="3 2"
              pointer-events="none"
            />
            <g
              v-if="layoutCanEdit"
              class="resize-handle"
              @mousedown="onSecurityZoneResizeMouseDown($event, zone)"
            >
              <rect
                :x="zone.x + zone.w - SEC_RESIZE_HANDLE"
                :y="zone.y + zone.h - SEC_RESIZE_HANDLE"
                :width="SEC_RESIZE_HANDLE"
                :height="SEC_RESIZE_HANDLE"
                rx="1.5"
                fill="#409eff"
                opacity="0.85"
              />
              <path
                :d="`M ${zone.x + zone.w - 8} ${zone.y + zone.h - 3} L ${zone.x + zone.w - 3} ${zone.y + zone.h - 3} L ${zone.x + zone.w - 3} ${zone.y + zone.h - 8} Z`"
                fill="#fff"
              />
            </g>
          </g>

          <g
            v-for="port in layout.ports"
            :key="port.id"
            class="port port-interactive"
            :class="{ selected: selectedPortId === port.id, linked: !!(port.peer_node_id || port.peer_device_id) }"
            @mousedown="onSecurityPortMouseDown($event, port)"
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
          </g>
        </g>
      </svg>

      <!-- Legacy editor -->
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
            :class="{ selected: selectedPortId === port.id, linked: !!(port.peer_node_id || port.peer_device_id) }"
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
      <span v-if="peerHintText" class="peer-hint">{{ peerHintText }}</span>
    </div>
    <p v-else-if="isServer" class="hint">
      <template v-if="layoutCanEdit">
        后面板：列表中编辑/删除扩展卡；面板上拖动卡体移动缩放
      </template>
      <template v-else>
        布局已锁定：不可添加/编辑扩展卡；可单击选中接口，双击或点「配置对端」编辑连接
      </template>
    </p>
    <p v-else-if="isSecurity" class="hint">
      <template v-if="layoutCanEdit">
        列表中编辑/删除接口区；面板上可拖动接口区移动缩放
      </template>
      <template v-else>布局已锁定：不可添加/编辑接口区；可单击选中接口，双击或点「配置对端」编辑连接</template>
    </p>
    <p v-else class="hint">
      <template v-if="layoutCanEdit">单击接口选中，双击配置对端；调整上方数量/上联位置后面板自动更新</template>
      <template v-else>布局已锁定：单击选中接口，双击或点「配置对端」编辑连接</template>
    </p>

    <Teleport to="body">
      <div
        v-if="regionEditorVisible"
        class="region-modal-mask"
        @click.self="closeRegionEditor"
        @mousedown.stop
      >
        <div class="region-modal" role="dialog" aria-modal="true">
          <div class="region-modal-header">
            <span class="region-modal-title">{{ regionEditorTitle }}</span>
            <button type="button" class="region-modal-close" @click="closeRegionEditor">×</button>
          </div>
          <div class="region-modal-body">
            <el-form label-width="96px">
              <template v-if="isSecurity">
                <el-form-item label="名称">
                  <el-input v-model="regionForm.zone_label" placeholder="WAN / LAN / MGMT" />
                </el-form-item>
                <el-form-item label="接口类型">
                  <el-select
                    v-model="regionForm.port_type"
                    style="width: 100%"
                    teleported
                    popper-class="region-modal-popper"
                  >
                    <el-option v-for="(label, key) in PORT_TYPE_LABELS" :key="key" :label="label" :value="key" />
                  </el-select>
                </el-form-item>
                <el-form-item label="接口数量">
                  <el-input-number
                    v-model="regionForm.count"
                    :min="1"
                    :max="128"
                    @change="onSecurityZoneCountChange"
                  />
                </el-form-item>
                <el-form-item label="排布">
                  <el-radio-group v-model="regionForm.zone_layout" size="small">
                    <el-radio-button
                      v-for="(label, key) in SECURITY_ZONE_LAYOUT_LABELS"
                      :key="key"
                      :value="key"
                    >
                      {{ label }}
                    </el-radio-button>
                  </el-radio-group>
                  <div class="field-hint" style="margin-top: 4px">
                    满 8 口自动换行（上下两行均分，如 WAN×8 → 4+4）
                  </div>
                </el-form-item>
                <el-form-item label="宽度">
                  <el-input-number
                    v-model="regionForm.layout_w"
                    :min="56"
                    :max="800"
                    controls-position="right"
                  />
                </el-form-item>
                <el-form-item label="高度">
                  <el-input-number
                    v-model="regionForm.layout_h"
                    :min="36"
                    :max="400"
                    controls-position="right"
                  />
                </el-form-item>
              </template>
              <template v-else>
                <el-form-item label="扩展卡类型">
                  <el-radio-group
                    v-model="regionForm.server_slot_kind"
                    class="slot-kind-radios"
                    @change="onRegionServerKindChange"
                  >
                    <el-radio-button
                      v-for="(label, key) in SERVER_SLOT_KIND_LABELS"
                      :key="key"
                      :value="key"
                    >
                      {{ label }}
                    </el-radio-button>
                  </el-radio-group>
                </el-form-item>
                <el-form-item label="放置">
                  <el-radio-group
                    v-model="regionForm.orientation"
                    size="small"
                    :disabled="serverForm.form_factor === 1"
                  >
                    <el-radio-button
                      v-for="(label, key) in SERVER_ORIENTATION_LABELS"
                      :key="key"
                      :value="key"
                    >
                      {{ label }}
                    </el-radio-button>
                  </el-radio-group>
                  <div class="field-hint" style="margin-top: 4px">
                    {{ serverForm.form_factor === 1 ? '1U 固定横向' : '横放贴网格 / 竖放从右依次排列' }}
                  </div>
                </el-form-item>
                <template v-if="!isPortlessServerSlot(regionForm.server_slot_kind)">
                  <el-form-item label="接口类型">
                    <el-select
                      v-model="regionForm.port_type"
                      style="width: 100%"
                      teleported
                      popper-class="region-modal-popper"
                    >
                      <el-option v-for="(label, key) in PORT_TYPE_LABELS" :key="key" :label="label" :value="key" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="接口数量">
                    <el-input-number
                      v-model="regionForm.count"
                      :min="1"
                      :max="SERVER_SLOT_PORT_MAX"
                      @change="onRegionPortCountChange"
                    />
                    <div v-if="regionForm.count > 5" class="field-hint" style="margin-top: 4px">
                      超过 5 个接口须为偶数（6/8/10）
                    </div>
                  </el-form-item>
                </template>
                <el-form-item v-else label="说明">
                  <span class="field-hint">
                    {{ regionForm.server_slot_kind === 'blank' ? '预留挡板，无接口' : 'RAID 卡无对外网络接口' }}
                  </span>
                </el-form-item>
              </template>
            </el-form>
          </div>
          <div class="region-modal-footer">
            <el-button @click="closeRegionEditor">取消</el-button>
            <el-button type="primary" @click="confirmRegionEditor">
              {{ regionEditorMode === 'add' ? '添加' : '保存' }}
            </el-button>
          </div>
        </div>
      </div>
    </Teleport>

    <el-dialog v-model="addSlotVisible" title="添加 Slot" width="420px" append-to-body>
      <el-form label-width="96px">
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
        <el-form-item label="对端来源">
          <el-radio-group :model-value="peerForm.source" @change="onPeerSourceChange">
            <el-radio-button value="define">设备定义</el-radio-button>
            <el-radio-button value="inventory">台账设备</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <template v-if="peerForm.source === 'define'">
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
        </template>
        <template v-else>
          <el-form-item label="台账设备">
            <el-select
              v-model="peerForm.peer_device_id"
              clearable
              filterable
              :loading="inventoryLoading"
              style="width: 100%"
              @change="onInventoryDeviceChange"
            >
              <el-option
                v-for="d in inventoryDevices"
                :key="d.id"
                :label="`${d.name || d.hostname}${d.rack_code ? ` · ${d.rack_code}` : ''}${d.u_position != null ? `/U${d.u_position}` : ''}`"
                :value="d.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item v-if="selectedInventoryDevice" label="设备位置">
            <span class="location-text">
              {{ selectedInventoryDevice.room_name || '—' }}
              / {{ selectedInventoryDevice.rack_code || '—' }}
              <template v-if="selectedInventoryDevice.u_position != null">
                / U{{ selectedInventoryDevice.u_position }}
              </template>
            </span>
          </el-form-item>
        </template>
        <el-form-item label="对端接口">
          <el-select
            v-model="peerForm.peer_port"
            clearable
            filterable
            :disabled="peerForm.source === 'define' ? !peerForm.peer_node_id : !peerForm.peer_device_id"
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

.panel-svg .panel-zone.card.blank {
  fill: rgba(144, 147, 153, 0.12);
  stroke: rgba(144, 147, 153, 0.45);
  stroke-dasharray: 4 3;
}

.panel-svg .blank-card-mark {
  fill: #909399;
  font-size: 11px;
  letter-spacing: 0.12em;
  pointer-events: none;
}

.panel-svg .panel-zone.onboard-zone {
  fill: rgba(103, 194, 58, 0.08);
  stroke: rgba(103, 194, 58, 0.4);
}

.panel-svg .panel-zone.psu-block {
  fill: rgba(255, 255, 255, 0.5);
  stroke: rgba(96, 98, 102, 0.35);
}

.security-zone-config .slot-block {
  min-width: 280px;
}

.security-zone-config .slot-block.active {
  outline: 1px solid #409eff;
  background: #f0f7ff;
}

.security-panel .sec-zone {
  cursor: move;
}

.security-panel .sec-zone.dragging {
  opacity: 0.92;
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
  pointer-events: none;
}

.security-panel .panel-zone.main {
  fill: rgba(255, 255, 255, 0.55);
  stroke: rgba(64, 158, 255, 0.35);
}

.security-panel .panel-zone.uplink {
  fill: rgba(230, 162, 60, 0.08);
  stroke: rgba(230, 162, 60, 0.45);
}

.panel-svg .port-label {
  font-size: 6.5px;
  fill: #606266;
}

.server-slot-bg {
  fill: rgba(255, 255, 255, 0.35);
  stroke: rgba(96, 98, 102, 0.25);
  stroke-width: 1;
}

.server-slot-bg.nic_1g {
  fill: rgba(64, 158, 255, 0.1);
  stroke: rgba(64, 158, 255, 0.45);
}

.server-slot-bg.nic_10g {
  fill: rgba(103, 194, 58, 0.1);
  stroke: rgba(103, 194, 58, 0.45);
}

.server-slot-bg.hba {
  fill: rgba(230, 162, 60, 0.1);
  stroke: rgba(230, 162, 60, 0.45);
}

.server-port .server-port-cavity {
  fill: rgba(48, 49, 51, 0.16);
  stroke-opacity: 0.35;
  stroke-width: 0.6;
  pointer-events: none;
}

.server-port .server-port-num {
  font-weight: 700;
  fill: #1f2d3d;
  paint-order: stroke fill;
  stroke: rgba(255, 255, 255, 0.88);
  stroke-width: 2.4px;
  pointer-events: none;
}

.server-port .server-port-type {
  font-size: 5.5px;
  font-weight: 600;
  fill: rgba(48, 49, 51, 0.72);
  letter-spacing: 0.02em;
  pointer-events: none;
}

.server-port:hover .port-face {
  filter: brightness(1.04);
}

.server-port.selected .port-face {
  filter: drop-shadow(0 0 2.5px rgba(64, 158, 255, 0.5));
}

.server-slot-bg.raid {
  fill: rgba(144, 147, 153, 0.12);
  stroke: rgba(144, 147, 153, 0.4);
}

.server-slot-bg.blank {
  fill: rgba(255, 255, 255, 0.25);
  stroke: rgba(144, 147, 153, 0.4);
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

.slot-edit-badge {
  cursor: pointer;
}

.slot-edit-badge-text {
  font-size: 8px;
  font-weight: 700;
  fill: #fff;
  pointer-events: none;
}

.server-slot-label {
  font-size: 8px;
  font-weight: 600;
  pointer-events: none;
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
  fill: #909399;
}

.slot-ref-label {
  font-size: 11px;
  font-weight: 700;
  fill: #c45656;
  pointer-events: none;
}

.region-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 240px;
  overflow-y: auto;
  margin-bottom: 4px;
}

.region-list-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.region-list-item:hover {
  border-color: #c6e2ff;
}

.region-list-item.active {
  border-color: #409eff;
  background: #f0f7ff;
}

.region-list-main {
  flex: 1;
  min-width: 0;
}

.region-list-title {
  font-weight: 600;
  font-size: 13px;
  color: #303133;
}

.region-list-summary {
  margin-top: 2px;
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.region-list-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
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

.size-row {
  flex-wrap: nowrap;
  gap: 8px;
}

.size-field {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  min-width: 0;
  margin: 0;
  color: inherit;
  font-weight: inherit;
}

.size-field > span {
  flex: 0 0 auto;
  color: #606266;
}

.size-field .el-input-number {
  flex: 1;
  width: auto;
  min-width: 0;
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

<style>
/* Teleport 到 body，使用非 scoped 样式保证可见 */
.region-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 4000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
}
.region-modal {
  width: min(480px, calc(100vw - 32px));
  max-height: calc(100vh - 48px);
  overflow: auto;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.18);
}
.region-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #ebeef5;
}
.region-modal-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}
.region-modal-close {
  border: none;
  background: transparent;
  font-size: 22px;
  line-height: 1;
  color: #909399;
  cursor: pointer;
  padding: 0 4px;
}
.region-modal-close:hover {
  color: #303133;
}
.region-modal-body {
  padding: 16px 16px 8px;
}
.region-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px 16px;
  border-top: 1px solid #ebeef5;
}
.region-modal-popper {
  z-index: 5000 !important;
}
.slot-kind-radios {
  display: flex;
  flex-wrap: wrap;
  width: 100%;
}
.slot-kind-radios .el-radio-button {
  margin-bottom: 6px;
}
.slot-kind-radios .el-radio-button__inner {
  padding: 8px 10px;
}
</style>
