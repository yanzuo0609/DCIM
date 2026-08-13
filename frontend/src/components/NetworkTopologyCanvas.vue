<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import TopologyGroupIcon from '@/components/TopologyGroupIcon.vue'
import {
  TOPOLOGY_DND_MIME,
  TOPOLOGY_GROUP_DND_MIME,
  readDeviceGroupDragData,
} from '@/utils/topologyDnd'
import type { NetworkLink, NetworkNode, SwitchSubtype } from '@/api/network'
import { nodeParentGroups } from '@/utils/deviceGroups'
import {
  buildGroupEdges,
  buildGroupGlyphs,
  ungroupedCanvasNodes,
  type CanvasGroupGlyph,
} from '@/utils/topologyGroupView'
import type { FabricRole } from '@/utils/wiringTypes'
import { DEVICE_GROUP_KIND_LABELS } from '@/utils/deviceGroupVisual'
import {
  normalizeLineStyle,
  strokeDasharrayOf,
  topologyLinkLabelPos,
  topologyLinkPath,
  type TopologyLineStyle,
} from '@/utils/topologyLinkStyle'

const props = defineProps<{
  nodes: NetworkNode[]
  links: NetworkLink[]
  selectedNodeId: string | null
  selectedLinkId?: string | null
  selectedGroupName?: string | null
  linkMode: boolean
  linkSourceId?: string | null
  stampMode?: boolean
  nodeLabStatus?: Record<string, string> | null
  /** devices=逐台；groups=按设备组简化架构 */
  viewMode?: 'devices' | 'groups'
  /** 组名 → 角色（图标） */
  groupRoles?: Record<string, FabricRole | null>
  /** 组视图中独立拖动后的图标位置；未记录则用成员质心 */
  groupPositions?: Record<string, { x: number; y: number }>
  /** 未单独指定样式的连线使用的默认风格 */
  lineStyle?: TopologyLineStyle
}>()

const emit = defineEmits<{
  selectNode: [id: string | null]
  selectLink: [id: string | null]
  selectGroup: [name: string | null]
  inspectGroup: [name: string]
  moveNode: [id: string, x: number, y: number]
  moveGroup: [name: string, x: number, y: number]
  placeNode: [id: string, x: number, y: number]
  placeDeviceGroup: [name: string, x: number, y: number]
  canvasClick: [x: number, y: number]
}>()

const ICON = 72
const GROUP_ICON = 88
const CULL_MARGIN = 240
const CULL_NODE_THRESHOLD = 350
const LABEL_NODE_THRESHOLD = 400
const LABEL_LINK_THRESHOLD = 200
const MIN_CANVAS_W = 1800
const MIN_CANVAS_H = 1200

const dragging = ref<{ id: string; offsetX: number; offsetY: number } | null>(null)
const draggingGroup = ref<{ name: string; offsetX: number; offsetY: number } | null>(null)
let groupDragMoved = false
const svgRef = ref<SVGSVGElement | null>(null)
const wrapRef = ref<HTMLElement | null>(null)
const dropActive = ref(false)
const hoveredLinkId = ref<string | null>(null)

const viewport = ref({ left: 0, top: 0, right: MIN_CANVAS_W, bottom: MIN_CANVAS_H })
let moveRaf = 0
let pendingMove: { id: string; x: number; y: number } | null = null
let scrollRaf = 0

const isGroupView = computed(() => props.viewMode === 'groups')

const roleMap = computed(() => {
  const m = new Map<string, FabricRole | null>()
  for (const [k, v] of Object.entries(props.groupRoles || {})) m.set(k, v)
  return m
})

const groupGlyphs = computed(() =>
  isGroupView.value
    ? buildGroupGlyphs(props.nodes, props.links, roleMap.value, props.groupPositions)
    : [],
)
const groupEdges = computed(() => (isGroupView.value ? buildGroupEdges(props.nodes, props.links) : []))
const loneNodes = computed(() =>
  isGroupView.value ? ungroupedCanvasNodes(props.nodes) : props.nodes.filter((n) => n.on_canvas !== false),
)

const canvasNodes = computed(() => props.nodes.filter((n) => n.on_canvas !== false))
const nodeMap = computed(() => new Map(canvasNodes.value.map((n) => [n.id, n])))
const canvasLinks = computed(() =>
  props.links.filter(
    (l) => nodeMap.value.has(l.source_node_id) && nodeMap.value.has(l.target_node_id),
  ),
)

const displayNodes = computed(() => (isGroupView.value ? loneNodes.value : canvasNodes.value))

const canvasSize = computed(() => {
  let maxX = MIN_CANVAS_W
  let maxY = MIN_CANVAS_H
  for (const n of displayNodes.value) {
    maxX = Math.max(maxX, n.pos_x + ICON + 160)
    maxY = Math.max(maxY, n.pos_y + ICON + 80)
  }
  for (const g of groupGlyphs.value) {
    maxX = Math.max(maxX, g.pos_x + GROUP_ICON + 160)
    maxY = Math.max(maxY, g.pos_y + GROUP_ICON + 80)
  }
  return { width: Math.ceil(maxX), height: Math.ceil(maxY) }
})

const useCull = computed(() => canvasNodes.value.length >= CULL_NODE_THRESHOLD)

const visibleNodes = computed(() => {
  const nodes = displayNodes.value
  if (!useCull.value) return nodes
  const { left, top, right, bottom } = viewport.value
  const pad = CULL_MARGIN
  return nodes.filter(
    (n) =>
      n.pos_x + ICON >= left - pad &&
      n.pos_x <= right + pad &&
      n.pos_y + ICON >= top - pad &&
      n.pos_y <= bottom + pad,
  )
})

const visibleGroups = computed(() => {
  if (!isGroupView.value) return [] as CanvasGroupGlyph[]
  const list = groupGlyphs.value
  if (!useCull.value) return list
  const { left, top, right, bottom } = viewport.value
  const pad = CULL_MARGIN
  return list.filter(
    (g) =>
      g.pos_x + GROUP_ICON >= left - pad &&
      g.pos_x <= right + pad &&
      g.pos_y + GROUP_ICON >= top - pad &&
      g.pos_y <= bottom + pad,
  )
})

const visibleNodeIds = computed(() => {
  if (!useCull.value) return null
  return new Set(visibleNodes.value.map((n) => n.id))
})

const visibleLinks = computed(() => {
  if (isGroupView.value) return []
  const links = canvasLinks.value
  const ids = visibleNodeIds.value
  if (!ids) return links
  return links.filter((l) => ids.has(l.source_node_id) || ids.has(l.target_node_id))
})

const showAllNodeLabels = computed(() => canvasNodes.value.length <= LABEL_NODE_THRESHOLD)
const showAllLinkLabels = computed(() => canvasLinks.value.length <= LABEL_LINK_THRESHOLD)

function groupCenter(g: CanvasGroupGlyph) {
  return { x: g.pos_x + GROUP_ICON / 2, y: g.pos_y + GROUP_ICON / 2 }
}

function groupEdgeEnds(edge: { sourceGroup: string; targetGroup: string }) {
  const src =
    groupGlyphs.value.find((g) => g.id === edge.sourceGroup) ||
    (edge.sourceGroup.startsWith('node:')
      ? displayNodes.value.find((n) => `node:${n.id}` === edge.sourceGroup)
      : null)
  const tgt =
    groupGlyphs.value.find((g) => g.id === edge.targetGroup) ||
    (edge.targetGroup.startsWith('node:')
      ? displayNodes.value.find((n) => `node:${n.id}` === edge.targetGroup)
      : null)
  if (!src || !tgt) return null
  const a =
    'pos_x' in src && 'count' in src
      ? groupCenter(src as CanvasGroupGlyph)
      : { x: (src as NetworkNode).pos_x + ICON / 2, y: (src as NetworkNode).pos_y + ICON / 2 }
  const b =
    'pos_x' in tgt && 'count' in tgt
      ? groupCenter(tgt as CanvasGroupGlyph)
      : { x: (tgt as NetworkNode).pos_x + ICON / 2, y: (tgt as NetworkNode).pos_y + ICON / 2 }
  return { a, b }
}

function resolvedLineStyle(link?: { line_style?: string | null }) {
  return normalizeLineStyle(link?.line_style || props.lineStyle)
}

function groupEdgePath(edge: { sourceGroup: string; targetGroup: string }) {
  const ends = groupEdgeEnds(edge)
  if (!ends) return ''
  return topologyLinkPath(ends.a.x, ends.a.y, ends.b.x, ends.b.y, resolvedLineStyle())
}

function groupEdgeLabelPos(edge: { sourceGroup: string; targetGroup: string }) {
  const ends = groupEdgeEnds(edge)
  if (!ends) return { x: 0, y: 0 }
  return topologyLinkLabelPos(ends.a.x, ends.a.y, ends.b.x, ends.b.y, resolvedLineStyle())
}

function nodeCenter(node: NetworkNode) {
  return { x: node.pos_x + ICON / 2, y: node.pos_y + ICON / 2 }
}

function iconSymbolId(node: NetworkNode): string {
  if (node.kind === 'switch') {
    const st = (node.port_layout?.switch_subtype as SwitchSubtype) || 'gigabit'
    if (st === 'ten_gigabit') return 'topo-ico-sw-10g'
    if (st === 'aggregation') return 'topo-ico-sw-agg'
    if (st === 'core') return 'topo-ico-sw-core'
    return 'topo-ico-sw-1g'
  }
  if (node.kind === 'server') {
    const v = node.port_layout?.server_form_factor ?? node.port_layout?.height_u
    if (v === 4) return 'topo-ico-srv-4'
    if (v === 2) return 'topo-ico-srv-2'
    return 'topo-ico-srv-1'
  }
  return Number(node.port_layout?.height_u) >= 2 ? 'topo-ico-sec-2' : 'topo-ico-sec-1'
}

function groupText(node: NetworkNode) {
  const groups = nodeParentGroups(node)
  if (!groups.length) return ''
  return groups[0]
}

function shouldShowNodeLabel(node: NetworkNode) {
  return (
    showAllNodeLabels.value ||
    props.selectedNodeId === node.id ||
    props.linkSourceId === node.id
  )
}

function shouldShowLinkLabel(link: NetworkLink) {
  return (
    showAllLinkLabels.value ||
    props.selectedLinkId === link.id ||
    hoveredLinkId.value === link.id
  )
}

function updateViewport() {
  const el = wrapRef.value
  if (!el) return
  const left = el.scrollLeft
  const top = el.scrollTop
  viewport.value = {
    left,
    top,
    right: left + el.clientWidth,
    bottom: top + el.clientHeight,
  }
}

function onWrapScroll() {
  if (scrollRaf) return
  scrollRaf = requestAnimationFrame(() => {
    scrollRaf = 0
    updateViewport()
  })
}

function svgPointFromEvent(event: MouseEvent | DragEvent) {
  const svg = svgRef.value
  if (!svg) return null
  const pt = svg.createSVGPoint()
  pt.x = event.clientX
  pt.y = event.clientY
  return pt.matrixTransform(svg.getScreenCTM()?.inverse())
}

function onNodeMouseDown(event: MouseEvent, node: NetworkNode) {
  event.stopPropagation()
  emit('selectGroup', null)
  emit('selectLink', null)
  emit('selectNode', node.id)
  if (props.linkMode) return
  const cursor = svgPointFromEvent(event)
  if (!cursor) return
  dragging.value = {
    id: node.id,
    offsetX: cursor.x - node.pos_x,
    offsetY: cursor.y - node.pos_y,
  }
}

function onGroupMouseDown(event: MouseEvent, g: CanvasGroupGlyph) {
  event.stopPropagation()
  if (event.button !== 0) return
  event.preventDefault()
  emit('selectNode', null)
  emit('selectLink', null)
  emit('selectGroup', g.name)
  if (props.linkMode || props.stampMode) return
  const cursor = svgPointFromEvent(event)
  if (!cursor) return
  groupDragMoved = false
  draggingGroup.value = {
    name: g.name,
    offsetX: cursor.x - g.pos_x,
    offsetY: cursor.y - g.pos_y,
  }
  window.addEventListener('mousemove', onWindowGroupMove)
  window.addEventListener('mouseup', onWindowGroupUp)
}

function onWindowGroupMove(event: MouseEvent) {
  if (!draggingGroup.value) return
  event.preventDefault()
  const cursor = svgPointFromEvent(event)
  if (!cursor) return
  const x = Math.max(0, cursor.x - draggingGroup.value.offsetX)
  const y = Math.max(0, cursor.y - draggingGroup.value.offsetY)
  groupDragMoved = true
  emit('moveGroup', draggingGroup.value.name, x, y)
}

function onWindowGroupUp() {
  window.removeEventListener('mousemove', onWindowGroupMove)
  window.removeEventListener('mouseup', onWindowGroupUp)
  onMouseUp()
}

function flushMove() {
  moveRaf = 0
  if (!pendingMove) return
  const m = pendingMove
  pendingMove = null
  emit('moveNode', m.id, m.x, m.y)
}

function onMouseMove(event: MouseEvent) {
  if (draggingGroup.value) return
  const cursor = svgPointFromEvent(event)
  if (!cursor) return
  if (!dragging.value) return
  pendingMove = {
    id: dragging.value.id,
    x: Math.max(0, cursor.x - dragging.value.offsetX),
    y: Math.max(0, cursor.y - dragging.value.offsetY),
  }
  if (!moveRaf) moveRaf = requestAnimationFrame(flushMove)
}

function onMouseUp() {
  if (pendingMove) flushMove()
  dragging.value = null
  draggingGroup.value = null
  window.removeEventListener('mousemove', onWindowGroupMove)
  window.removeEventListener('mouseup', onWindowGroupUp)
}

function onWrapMouseLeave() {
  if (draggingGroup.value) return
  onMouseUp()
}

function onBackgroundClick(event: MouseEvent) {
  if (props.linkMode) return
  const target = event.target as Element | null
  if (target?.closest?.('.node') || target?.closest?.('.link-hit') || target?.closest?.('.group-node'))
    return
  const cursor = svgPointFromEvent(event)
  if (!cursor) {
    emit('selectLink', null)
    emit('selectNode', null)
    emit('selectGroup', null)
    return
  }
  if (props.stampMode) {
    emit('canvasClick', Math.max(0, cursor.x - ICON / 2), Math.max(0, cursor.y - ICON / 2))
    return
  }
  emit('selectLink', null)
  emit('selectNode', null)
  emit('selectGroup', null)
  emit('canvasClick', cursor.x, cursor.y)
}

function onNodeClick(event: MouseEvent, node: NetworkNode) {
  event.stopPropagation()
  emit('selectGroup', null)
  emit('selectLink', null)
  emit('selectNode', node.id)
}

function onGroupClick(event: MouseEvent, g: CanvasGroupGlyph) {
  event.stopPropagation()
  if (groupDragMoved) return
  emit('selectNode', null)
  emit('selectLink', null)
  emit('selectGroup', g.name)
}

function onGroupContextMenu(event: MouseEvent, g: CanvasGroupGlyph) {
  event.preventDefault()
  event.stopPropagation()
  emit('selectNode', null)
  emit('selectLink', null)
  emit('selectGroup', g.name)
  emit('inspectGroup', g.name)
}

function onLinkClick(event: MouseEvent, link: NetworkLink) {
  event.stopPropagation()
  if (props.linkMode || props.stampMode) return
  emit('selectGroup', null)
  emit('selectNode', null)
  emit('selectLink', link.id)
}

function acceptsDrag(types: string[]) {
  return (
    types.includes(TOPOLOGY_GROUP_DND_MIME) ||
    types.includes(TOPOLOGY_DND_MIME) ||
    types.includes('text/plain')
  )
}

function onDragOver(event: DragEvent) {
  if (!event.dataTransfer) return
  const types = Array.from(event.dataTransfer.types || [])
  if (!acceptsDrag(types)) return
  event.preventDefault()
  event.dataTransfer.dropEffect = 'copy'
  dropActive.value = true
}

function onDragLeave() {
  dropActive.value = false
}

function onDrop(event: DragEvent) {
  event.preventDefault()
  dropActive.value = false
  const cursor = svgPointFromEvent(event)
  if (!cursor) return
  const x = Math.max(0, cursor.x - ICON / 2)
  const y = Math.max(0, cursor.y - ICON / 2)
  const group = readDeviceGroupDragData(event.dataTransfer)
  if (group?.name) {
    emit('placeDeviceGroup', group.name, x, y)
    return
  }
  const id =
    event.dataTransfer?.getData(TOPOLOGY_DND_MIME) ||
    event.dataTransfer?.getData('text/plain') ||
    ''
  if (!id || id.startsWith('group:')) return
  emit('placeNode', id, x, y)
}

function linkPath(link: NetworkLink) {
  const source = nodeMap.value.get(link.source_node_id)
  const target = nodeMap.value.get(link.target_node_id)
  if (!source || !target) return ''
  const s = nodeCenter(source)
  const t = nodeCenter(target)
  return topologyLinkPath(s.x, s.y, t.x, t.y, resolvedLineStyle(link))
}

function linkLabelPos(link: NetworkLink) {
  const source = nodeMap.value.get(link.source_node_id)
  const target = nodeMap.value.get(link.target_node_id)
  if (!source || !target) return { x: 0, y: 0 }
  const s = nodeCenter(source)
  const t = nodeCenter(target)
  return topologyLinkLabelPos(s.x, s.y, t.x, t.y, resolvedLineStyle(link))
}

function resolveLinkSpeed(link: NetworkLink): string {
  const raw = String(link.speed || link.media || '').trim().toUpperCase()
  if (raw) return raw.replace('_', '')
  const src = nodeMap.value.get(link.source_node_id)
  const tgt = nodeMap.value.get(link.target_node_id)
  const findType = (node: NetworkNode | undefined, portRef: string) => {
    if (!node?.port_layout?.ports?.length) return ''
    const p = node.port_layout.ports.find(
      (x) => x.id === portRef || x.label === portRef || String(x.label) === portRef,
    )
    return String(p?.port_type || '').toLowerCase()
  }
  const types = [findType(src, link.source_port), findType(tgt, link.target_port)]
  if (types.some((t) => t === '40_100g' || t === '100g' || t === '40g')) return '100G'
  if (types.some((t) => t === '10g' || t === '25g')) return '10G'
  if (types.some((t) => t === '1g' || t === 'bmc')) return '1G'
  return ''
}

function linkColor(link: NetworkLink) {
  const speed = resolveLinkSpeed(link)
  if (
    speed.includes('100G') ||
    speed.includes('40G') ||
    speed.includes('400G') ||
    speed.includes('40100')
  ) {
    return '#1a1a1a'
  }
  if (speed.includes('1G') && !speed.includes('10G') && !speed.includes('100G')) {
    return '#6F4E37'
  }
  if (speed.includes('10G') || speed.includes('25G')) {
    return '#2563eb'
  }
  if (link.link_type === 'switch_switch') return '#1a1a1a'
  if (link.link_type === 'switch_security') return '#6F4E37'
  return '#2563eb'
}

onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateViewport)
  window.removeEventListener('mousemove', onWindowGroupMove)
  window.removeEventListener('mouseup', onWindowGroupUp)
  if (moveRaf) cancelAnimationFrame(moveRaf)
  if (scrollRaf) cancelAnimationFrame(scrollRaf)
})

watch(
  () => canvasNodes.value.length,
  async () => {
    await nextTick()
    updateViewport()
  },
)
</script>

<template>
  <div
    ref="wrapRef"
    class="canvas-wrap"
    :class="{
      'drop-active': dropActive,
      'link-mode': linkMode,
      'stamp-mode': stampMode && !linkMode,
      'group-dragging': !!draggingGroup,
    }"
    @mousemove="onMouseMove"
    @mouseup="onMouseUp"
    @mouseleave="onWrapMouseLeave"
    @scroll.passive="onWrapScroll"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <svg
      ref="svgRef"
      class="canvas"
      :width="canvasSize.width"
      :height="canvasSize.height"
      :viewBox="`0 0 ${canvasSize.width} ${canvasSize.height}`"
      @click="onBackgroundClick"
    >
      <defs>
        <marker id="topo-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L0,6 L6,3 z" fill="#606266" />
        </marker>

        <!-- 设备图标符号（复用，避免数千 foreignObject） -->
        <symbol id="topo-ico-sw-1g" viewBox="0 0 48 48">
          <rect x="6" y="16" width="36" height="18" rx="3" fill="#2f5f9e" />
          <rect x="10" y="20" width="28" height="4" rx="1" fill="#fff" opacity="0.35" />
          <circle cx="12" cy="29" r="1.4" fill="#fff" opacity="0.85" />
          <circle cx="17" cy="29" r="1.4" fill="#fff" opacity="0.85" />
          <circle cx="22" cy="29" r="1.4" fill="#fff" opacity="0.55" />
          <circle cx="27" cy="29" r="1.4" fill="#fff" opacity="0.85" />
          <circle cx="32" cy="29" r="1.4" fill="#fff" opacity="0.55" />
          <circle cx="37" cy="29" r="1.4" fill="#fff" opacity="0.85" />
        </symbol>
        <symbol id="topo-ico-sw-10g" viewBox="0 0 48 48">
          <rect x="5" y="14" width="38" height="22" rx="3" fill="#2f5f9e" />
          <rect x="9" y="18" width="5" height="12" rx="1" fill="#fff" opacity="0.3" />
          <rect x="16" y="18" width="5" height="12" rx="1" fill="#fff" opacity="0.45" />
          <rect x="23" y="18" width="5" height="12" rx="1" fill="#fff" opacity="0.3" />
          <rect x="30" y="18" width="5" height="12" rx="1" fill="#fff" opacity="0.45" />
          <rect x="37" y="18" width="3" height="12" rx="0.8" fill="#fff" opacity="0.25" />
        </symbol>
        <symbol id="topo-ico-sw-agg" viewBox="0 0 48 48">
          <rect x="5" y="14" width="38" height="22" rx="3" fill="#2f5f9e" />
          <rect x="9" y="18" width="16" height="12" rx="1.5" fill="#fff" opacity="0.28" />
          <rect x="27" y="18" width="12" height="12" rx="1.5" fill="#fff" opacity="0.45" />
          <circle cx="12" cy="24" r="1.2" fill="#fff" />
          <circle cx="17" cy="24" r="1.2" fill="#fff" />
          <circle cx="22" cy="24" r="1.2" fill="#fff" opacity="0.6" />
          <circle cx="31" cy="24" r="1.5" fill="#fff" />
          <circle cx="35" cy="24" r="1.5" fill="#fff" />
        </symbol>
        <symbol id="topo-ico-sw-core" viewBox="0 0 48 48">
          <rect x="5" y="14" width="38" height="22" rx="3" fill="#2f5f9e" />
          <rect x="9" y="17" width="30" height="3.2" rx="0.8" fill="#fff" opacity="0.4" />
          <rect x="9" y="22" width="30" height="3.2" rx="0.8" fill="#fff" opacity="0.28" />
          <rect x="9" y="27" width="30" height="3.2" rx="0.8" fill="#fff" opacity="0.28" />
          <circle cx="36" cy="18.6" r="1.1" fill="#fff" />
        </symbol>
        <symbol id="topo-ico-srv-1" viewBox="0 0 48 48">
          <rect x="5" y="17" width="38" height="14" rx="2.5" fill="#2f5f9e" />
          <rect x="9" y="20" width="16" height="8" rx="1" fill="#fff" opacity="0.3" />
          <rect x="28" y="20" width="5" height="8" rx="1" fill="#fff" opacity="0.45" />
          <rect x="35" y="20" width="5" height="8" rx="1" fill="#fff" opacity="0.45" />
          <circle cx="11" cy="28" r="1.1" fill="#fff" />
        </symbol>
        <symbol id="topo-ico-srv-2" viewBox="0 0 48 48">
          <rect x="8" y="10" width="32" height="28" rx="3" fill="#2f5f9e" />
          <rect x="12" y="14" width="10" height="7" rx="1" fill="#fff" opacity="0.35" />
          <rect x="26" y="14" width="10" height="7" rx="1" fill="#fff" opacity="0.35" />
          <rect x="12" y="24" width="10" height="7" rx="1" fill="#fff" opacity="0.28" />
          <rect x="26" y="24" width="10" height="7" rx="1" fill="#fff" opacity="0.28" />
          <circle cx="34" cy="34" r="1.4" fill="#fff" />
        </symbol>
        <symbol id="topo-ico-srv-4" viewBox="0 0 48 48">
          <rect x="13" y="5" width="22" height="38" rx="3" fill="#2f5f9e" />
          <rect x="16" y="9" width="16" height="5" rx="1" fill="#4a7ab8" />
          <rect x="16" y="17" width="16" height="3.2" rx="0.7" fill="#fff" opacity="0.3" />
          <rect x="16" y="22" width="16" height="3.2" rx="0.7" fill="#fff" opacity="0.3" />
          <rect x="16" y="27" width="16" height="3.2" rx="0.7" fill="#fff" opacity="0.3" />
          <rect x="16" y="32" width="16" height="3.2" rx="0.7" fill="#fff" opacity="0.3" />
        </symbol>
        <symbol id="topo-ico-sec-1" viewBox="0 0 48 48">
          <path
            d="M24 8 L37 13.5 V23 C37 32 30.5 38.5 24 42 C17.5 38.5 11 32 11 23 V13.5 Z"
            fill="#2f5f9e"
          />
          <path
            d="M24 14 L31 17 V23.5 C31 28.5 27.5 32.2 24 34.2 C20.5 32.2 17 28.5 17 23.5 V17 Z"
            fill="#fff"
            opacity="0.28"
          />
        </symbol>
        <symbol id="topo-ico-sec-2" viewBox="0 0 48 48">
          <rect x="10" y="34" width="28" height="6" rx="1.5" fill="#4a7ab8" />
          <path
            d="M24 6 L38 12 V22 C38 32 31 39 24 43 C17 39 10 32 10 22 V12 Z"
            fill="#2f5f9e"
          />
          <path
            d="M24 12 L32 15.5 V23 C32 29 28 33.5 24 36 C20 33.5 16 29 16 23 V15.5 Z"
            fill="#fff"
            opacity="0.28"
          />
        </symbol>
      </defs>

      <g class="links">
        <template v-if="isGroupView">
          <g v-for="edge in groupEdges" :key="edge.id" class="link-group">
            <path
              class="link-line"
              :d="groupEdgePath(edge)"
              fill="none"
              stroke="#909399"
              :stroke-width="Math.min(6, 2 + edge.count * 0.4)"
              :stroke-dasharray="strokeDasharrayOf(resolvedLineStyle())"
              marker-end="url(#topo-arrow)"
              pointer-events="none"
            />
            <text
              :x="groupEdgeLabelPos(edge).x"
              :y="groupEdgeLabelPos(edge).y"
              class="link-label"
              text-anchor="middle"
            >
              {{ edge.count }} 条
            </text>
          </g>
        </template>
        <template v-else>
          <g
            v-for="link in visibleLinks"
            :key="link.id"
            class="link-group"
            :class="{ selected: selectedLinkId === link.id }"
            @mouseenter="hoveredLinkId = link.id"
            @mouseleave="hoveredLinkId = null"
          >
            <path
              class="link-hit"
              :d="linkPath(link)"
              fill="none"
              stroke="transparent"
              :stroke-width="showAllLinkLabels ? 14 : 10"
              @click.stop="onLinkClick($event, link)"
            />
            <path
              class="link-line"
              :d="linkPath(link)"
              fill="none"
              :stroke="selectedLinkId === link.id ? '#f56c6c' : linkColor(link)"
              :stroke-width="selectedLinkId === link.id ? 3.2 : 2"
              :stroke-dasharray="strokeDasharrayOf(resolvedLineStyle(link))"
              marker-end="url(#topo-arrow)"
              pointer-events="none"
            />
            <text
              v-if="shouldShowLinkLabel(link)"
              :x="linkLabelPos(link).x"
              :y="linkLabelPos(link).y"
              class="link-label"
              text-anchor="middle"
              @click.stop="onLinkClick($event, link)"
            >
              {{ link.label || `${link.source_port} → ${link.target_port}` }}
            </text>
          </g>
        </template>
      </g>

      <g class="nodes">
        <g
          v-for="g in visibleGroups"
          :key="`grp-${g.id}`"
          class="group-node"
          :class="{ selected: selectedGroupName === g.name }"
          :transform="`translate(${g.pos_x}, ${g.pos_y})`"
          @mousedown="onGroupMouseDown($event, g)"
          @click.stop="onGroupClick($event, g)"
          @contextmenu.prevent="onGroupContextMenu($event, g)"
        >
          <rect
            v-if="selectedGroupName === g.name"
            x="-5"
            y="-5"
            :width="GROUP_ICON + 10"
            :height="GROUP_ICON + 10"
            rx="14"
            fill="none"
            stroke="#409eff"
            stroke-width="2"
          />
          <rect
            class="group-hit"
            :width="GROUP_ICON"
            :height="GROUP_ICON"
            rx="12"
            fill="transparent"
          />
          <foreignObject :width="GROUP_ICON" :height="GROUP_ICON" pointer-events="none">
            <div class="group-ico-wrap" xmlns="http://www.w3.org/1999/xhtml">
              <TopologyGroupIcon
                :kind="g.kind"
                :size="GROUP_ICON"
                :selected="selectedGroupName === g.name"
                :count="g.count"
              />
            </div>
          </foreignObject>
          <text :x="GROUP_ICON / 2" :y="GROUP_ICON + 14" text-anchor="middle" class="node-name">
            {{ g.name }}
          </text>
          <text :x="GROUP_ICON / 2" :y="GROUP_ICON + 28" text-anchor="middle" class="node-group">
            {{ DEVICE_GROUP_KIND_LABELS[g.kind] }}{{ g.intraLinkCount ? ` · 组内 ${g.intraLinkCount} 线` : '' }}
          </text>
        </g>

        <g
          v-for="node in visibleNodes"
          :key="node.id"
          class="node"
          :class="{
            selected: selectedNodeId === node.id,
            'link-source': linkSourceId === node.id,
            'link-target': linkMode,
          }"
          :transform="`translate(${node.pos_x}, ${node.pos_y})`"
          @mousedown="onNodeMouseDown($event, node)"
          @click.stop="onNodeClick($event, node)"
        >
          <rect
            v-if="selectedNodeId === node.id || linkSourceId === node.id"
            x="-2"
            y="-2"
            :width="ICON + 4"
            :height="ICON + 4"
            rx="8"
            fill="none"
            stroke="#409eff"
            stroke-width="2"
          />
          <use :href="`#${iconSymbolId(node)}`" :width="ICON" :height="ICON" />
          <text
            v-if="shouldShowNodeLabel(node)"
            :x="ICON / 2"
            :y="ICON + 14"
            text-anchor="middle"
            class="node-name"
          >
            {{ node.name }}
          </text>
          <text
            v-if="shouldShowNodeLabel(node) && groupText(node)"
            :x="ICON / 2"
            :y="ICON + 28"
            text-anchor="middle"
            class="node-group"
          >
            {{ groupText(node) }}
          </text>
          <circle
            v-if="nodeLabStatus?.[node.id]"
            :cx="ICON - 6"
            :cy="8"
            r="5"
            class="lab-dot"
            :class="`lab-${nodeLabStatus[node.id]}`"
          />
        </g>
      </g>
    </svg>
    <div v-if="!canvasNodes.length" class="canvas-empty">
      {{
        stampMode
          ? '点击画布连续放置选中模型；也可在模型上右键批量部署'
          : '拖拽/点击模型放置，或右键模型指定数量批量部署；也可拖入设备组'
      }}
    </div>
    <div v-else-if="isGroupView" class="canvas-stats">
      组视图 · {{ groupGlyphs.length }} 组 · 未分组 {{ loneNodes.length }} 台 · 组间线
      {{ groupEdges.length }} · 拖动只移动当前组图标，右键查看详情
    </div>
    <div v-else-if="useCull" class="canvas-stats">
      可见 {{ visibleNodes.length }}/{{ canvasNodes.length }} 台 · 连线
      {{ visibleLinks.length }}/{{ canvasLinks.length }}
    </div>
  </div>
</template>

<style scoped>
.canvas-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: auto;
  background:
    linear-gradient(#e8edf3 1px, transparent 1px) 0 0 / 24px 24px,
    linear-gradient(90deg, #e8edf3 1px, transparent 1px) 0 0 / 24px 24px,
    #f4f7fb;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
}

.canvas-wrap.drop-active {
  outline: 2px dashed #409eff;
  outline-offset: -2px;
}

.canvas-wrap.link-mode {
  cursor: crosshair;
}

.canvas-wrap.stamp-mode {
  cursor: copy;
}

.canvas {
  display: block;
  min-width: 1800px;
  min-height: 1200px;
}

.node {
  cursor: grab;
}

.group-node {
  cursor: grab;
}

.canvas-wrap.group-dragging,
.canvas-wrap.group-dragging .group-node {
  cursor: grabbing;
}

.group-ico-wrap {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.node.link-target {
  cursor: crosshair;
}

.node-name {
  fill: #303133;
  font-size: 12px;
  font-weight: 600;
  pointer-events: none;
}

.node-group {
  fill: #909399;
  font-size: 10px;
  pointer-events: none;
}

.link-hit {
  cursor: pointer;
}

.link-label {
  fill: #606266;
  font-size: 11px;
  cursor: pointer;
  pointer-events: auto;
}

.link-group.selected .link-label {
  fill: #f56c6c;
  font-weight: 600;
}

.canvas-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  font-size: 14px;
  pointer-events: none;
}

.canvas-stats {
  position: absolute;
  right: 10px;
  bottom: 8px;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.85);
  color: #909399;
  font-size: 11px;
  pointer-events: none;
}

.lab-dot {
  stroke: #fff;
  stroke-width: 1.5;
}
.lab-dot.lab-running {
  fill: #67c23a;
}
.lab-dot.lab-stopped {
  fill: #909399;
}
.lab-dot.lab-error {
  fill: #f56c6c;
}
</style>
