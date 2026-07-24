<script setup lang="ts">
import { computed, ref } from 'vue'
import type { NetworkLink, NetworkNode } from '@/api/network'
import { NODE_KIND_COLORS, NODE_KIND_LABELS } from '@/api/network'

const props = defineProps<{
  nodes: NetworkNode[]
  links: NetworkLink[]
  selectedNodeId: string | null
  linkMode: boolean
}>()

const emit = defineEmits<{
  selectNode: [id: string | null]
  moveNode: [id: string, x: number, y: number]
  canvasClick: []
}>()

const NODE_W = 140
const NODE_H = 56

const dragging = ref<{ id: string; offsetX: number; offsetY: number } | null>(null)
const svgRef = ref<SVGSVGElement | null>(null)

const nodeMap = computed(() => new Map(props.nodes.map((n) => [n.id, n])))

function nodeCenter(node: NetworkNode) {
  return { x: node.pos_x + NODE_W / 2, y: node.pos_y + NODE_H / 2 }
}

function onNodeMouseDown(event: MouseEvent, node: NetworkNode) {
  event.stopPropagation()
  if (props.linkMode) {
    emit('selectNode', node.id)
    return
  }
  const svg = svgRef.value
  if (!svg) return
  const pt = svg.createSVGPoint()
  pt.x = event.clientX
  pt.y = event.clientY
  const cursor = pt.matrixTransform(svg.getScreenCTM()?.inverse())
  dragging.value = {
    id: node.id,
    offsetX: cursor.x - node.pos_x,
    offsetY: cursor.y - node.pos_y,
  }
  emit('selectNode', node.id)
}

function onMouseMove(event: MouseEvent) {
  if (!dragging.value || !svgRef.value) return
  const pt = svgRef.value.createSVGPoint()
  pt.x = event.clientX
  pt.y = event.clientY
  const cursor = pt.matrixTransform(svgRef.value.getScreenCTM()?.inverse())
  emit(
    'moveNode',
    dragging.value.id,
    Math.max(0, cursor.x - dragging.value.offsetX),
    Math.max(0, cursor.y - dragging.value.offsetY),
  )
}

function onMouseUp() {
  dragging.value = null
}

function onBackgroundClick() {
  if (props.linkMode) return
  emit('selectNode', null)
  emit('canvasClick')
}

function linkPath(link: NetworkLink) {
  const source = nodeMap.value.get(link.source_node_id)
  const target = nodeMap.value.get(link.target_node_id)
  if (!source || !target) return ''
  const s = nodeCenter(source)
  const t = nodeCenter(target)
  const mx = (s.x + t.x) / 2
  return `M ${s.x} ${s.y} Q ${mx} ${s.y} ${t.x} ${t.y}`
}

function linkColor(linkType: string) {
  if (linkType === 'switch_switch') return '#909399'
  if (linkType === 'switch_security') return '#e6a23c'
  return '#67c23a'
}
</script>

<template>
  <div class="canvas-wrap" @mousemove="onMouseMove" @mouseup="onMouseUp" @mouseleave="onMouseUp">
    <svg ref="svgRef" class="canvas" @click="onBackgroundClick">
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L0,6 L6,3 z" fill="#909399" />
        </marker>
      </defs>
      <g class="links">
        <g v-for="link in links" :key="link.id">
          <path
            :d="linkPath(link)"
            fill="none"
            :stroke="linkColor(link.link_type)"
            stroke-width="2"
            marker-end="url(#arrow)"
          />
          <text
            v-if="link.label || link.source_port"
            :x="(nodeMap.get(link.source_node_id)?.pos_x || 0) + NODE_W / 2"
            :y="(nodeMap.get(link.source_node_id)?.pos_y || 0) - 8"
            class="link-label"
            text-anchor="middle"
          >
            {{ link.label || `${link.source_port} → ${link.target_port}` }}
          </text>
        </g>
      </g>
      <g class="nodes">
        <g
          v-for="node in nodes"
          :key="node.id"
          class="node"
          :class="{ selected: selectedNodeId === node.id, 'link-target': linkMode }"
          :transform="`translate(${node.pos_x}, ${node.pos_y})`"
          @mousedown="onNodeMouseDown($event, node)"
        >
          <rect
            :width="NODE_W"
            :height="NODE_H"
            rx="8"
            :fill="NODE_KIND_COLORS[node.kind]"
            opacity="0.92"
          />
          <text x="12" y="22" class="node-kind">{{ NODE_KIND_LABELS[node.kind] }}</text>
          <text x="12" y="42" class="node-name">{{ node.name }}</text>
        </g>
      </g>
    </svg>
  </div>
</template>

<style scoped>
.canvas-wrap {
  width: 100%;
  height: 100%;
  overflow: auto;
  background:
    linear-gradient(#eef1f6 1px, transparent 1px) 0 0 / 20px 20px,
    linear-gradient(90deg, #eef1f6 1px, transparent 1px) 0 0 / 20px 20px,
    #f8fafc;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
}

.canvas {
  width: 1800px;
  height: 1200px;
  display: block;
}

.node {
  cursor: grab;
}

.node.selected rect {
  stroke: #303133;
  stroke-width: 3;
}

.node.link-target {
  cursor: crosshair;
}

.node-kind {
  fill: rgba(255, 255, 255, 0.85);
  font-size: 11px;
}

.node-name {
  fill: #fff;
  font-size: 13px;
  font-weight: 600;
}

.link-label {
  fill: #606266;
  font-size: 11px;
}
</style>
