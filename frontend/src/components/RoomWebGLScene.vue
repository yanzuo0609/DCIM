<script setup lang="ts">
/**
 * WebGL 真三维机房 — 排×列场景网格（机柜 / 立柱 / 列头柜）
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { CSS2DRenderer, CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js'
import {
  fetchDashboardRoomLayout,
  fetchDashboardRooms,
  type RoomMonitorLayout,
  type RoomMonitorOption,
  type RoomMonitorRack,
} from '@/api/dashboard'
import { getRackLayout, type Rack, type RackLayoutSlot } from '@/api/rack'
import { updateRoom } from '@/api/room'
import RackCabinet from '@/components/RackCabinet.vue'
import {
  applyGridSize,
  buildFullRackGrid,
  cellKindLabel,
  clearAt,
  countRackSlots,
  getCellProp,
  getRow,
  isFixedKind,
  isPillarKind,
  isPlaceableKind,
  moveFixed,
  parseSceneLayout,
  placeAt,
  planSceneRow,
  toPersistLayout,
  type CellKind,
  type CellProp,
  type SceneLayout,
} from '@/utils/roomSceneLayout'
import { buildPresetSlotCodes, expandRowPrefixes, normalizeSlotCodesMatrix, renumberRackSlots } from '@/utils/roomSlotCodes'

const props = withDefaults(
  defineProps<{
    preferredRoomId?: string | null
    quality?: '1' | '2'
    /** 内置库当前选中的笔刷（点击格子替换） */
    brushKind?: CellKind | null
    /** 自定义模型等附加属性 */
    brushMeta?: CellProp | null
  }>(),
  {
    preferredRoomId: null,
    quality: '1',
    brushKind: null,
    brushMeta: null,
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
  ready: []
  'edit-mode-change': [editing: boolean]
}>()

const STORAGE_KEY = 'dcim.cockpit.selectedRoomId'
const RACK_W = 0.6
const RACK_D = 1.0
const RACK_H = 2.0
const AISLE = 1.35
const GAP = 0.04

const hostRef = ref<HTMLElement | null>(null)
const rooms = ref<RoomMonitorOption[]>([])
const layout = ref<RoomMonitorLayout | null>(null)
const selectedRoomId = ref('')
const selectedRackId = ref<string | null>(null)
const loading = ref(false)
const errorMsg = ref('')
const savingLayout = ref(false)

const sceneLayout = ref<SceneLayout | null>(null)
const dirty = ref(false)
const editRows = ref(1)
const editCols = ref(1)
const sceneEditMode = ref(false)
const selectedCell = ref<{ row: number; col: number; kind: CellKind } | null>(null)

type EditSnapshot = {
  scene: SceneLayout
  slotCodes: string[][]
  codePrefix: string | null | undefined
  labelSide: 'left' | 'right'
  editRows: number
  editCols: number
}

const UNDO_LIMIT = 40
const undoStack = ref<EditSnapshot[]>([])
let editBaseline: EditSnapshot | null = null

const canUndo = computed(() => sceneEditMode.value && undoStack.value.length > 0)

/** 编号方向：左编号 / 右编号（标签位置 + 连续编号列序） */
const labelSide = ref<'left' | 'right'>('left')
/** 编号显隐模式 */
const labelVisMode = ref<'all' | 'hide_all' | 'row_only' | 'row_hide'>('all')
const labelFocusRow = ref(1)

const showCodeBatch = ref(false)
const codeBatchPrefix = ref('A')
const codeBatchStart = ref(1)
const codeBatchSaving = ref(false)
const editingCode = ref('')
const savingCode = ref(false)

const rackDialogVisible = ref(false)
const rackDialogLoading = ref(false)
const rackDialogError = ref('')
const rackDialogRack = ref<Rack | null>(null)
const rackDialogSlots = ref<RackLayoutSlot[]>([])
const rackDialogPower = ref(0)

const roomOptions = computed(() =>
  rooms.value.map((r) => ({
    id: r.id,
    label:
      [r.datacenter_name, r.name].filter(Boolean).join(' / ') +
      (r.rack_count ? `（${r.rack_count}柜）` : ''),
  })),
)

const selectedRack = computed(() =>
  layout.value?.racks.find((r) => r.id === selectedRackId.value) || null,
)

const selectedSlotPos = computed(() => {
  const rack = selectedRack.value
  if (!rack) return null
  return { row: rack.row_no, col: rack.column_no }
})

const selectedCellLabel = computed(() => {
  const sel = selectedCell.value
  if (!sel || !sceneLayout.value) return '空位'
  if (sel.kind === 'custom') {
    return getCellProp(sceneLayout.value, sel.row, sel.col)?.label || '自定义'
  }
  return cellKindLabel(sel.kind)
})

let renderer: THREE.WebGLRenderer | null = null
let labelRenderer: CSS2DRenderer | null = null
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let controls: OrbitControls | null = null
let roomGroup: THREE.Group | null = null
let animId = 0
let resizeObs: ResizeObserver | null = null
const rackMeshes = new Map<string, THREE.Object3D>()
const fixedMeshes = new Map<string, THREE.Group>()
/** 场景格位 → 物体组，用于选中高亮 */
const cellGroups = new Map<string, THREE.Group>()
const cellPickTargets: THREE.Object3D[] = []
const labelNodes = new Map<string, HTMLElement>()
const labelObjects = new Map<string, CSS2DObject>()
const raycaster = new THREE.Raycaster()
const pointer = new THREE.Vector2()
const dragPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0)
const dragTarget = new THREE.Vector3()
let dragMoveRaf = 0
let pendingDragEvent: PointerEvent | null = null
let rebuildRaf = 0
let selectionMesh: THREE.Mesh | null = null
let hoverMesh: THREE.Mesh | null = null
let hoverKey = ''
let hoverRaf = 0
let pendingHoverEvent: PointerEvent | null = null

interface GridMeta {
  startX: number
  startZ: number
  cols: number
  rows: number
  pitchX: number
  pitchZ: number
  roomW: number
  roomD: number
}

let gridMeta: GridMeta | null = null

let pointerDownXY = { x: 0, y: 0 }
let draggingFixed = false
let dragMoved = false
let dragFrom: { row: number; col: number; kind: CellKind } | null = null
let dragPreview: { row: number; col: number } | null = null

function utilColor(util: number, status: string): number {
  const st = (status || '').toLowerCase()
  if (st.includes('fault') || st.includes('error') || st.includes('故障') || util >= 85) {
    return 0xe35d5b
  }
  if (util >= 60) return 0xf0b429
  return 0x3aa0ff
}

function emitStats() {
  const data = layout.value
  const racks = data?.racks || []
  const deviceTotal = racks.reduce((s, r) => s + (r.device_count || 0), 0)
  const danger = racks.filter((r) => (r.utilization || 0) >= 85).length
  const fault = racks.filter((r) => {
    const st = (r.status || '').toLowerCase()
    return st.includes('fault') || st.includes('error') || st.includes('故障') || st === 'alarm'
  }).length
  const total = sceneLayout.value
    ? countRackSlots(sceneLayout.value)
    : (data?.row_layout || []).reduce((s, n) => s + n, 0)
  const occupied = racks.length
  emit('stats', {
    roomId: selectedRoomId.value,
    roomTitle:
      [data?.datacenter_name, data?.location, data?.room_name].filter(Boolean).join(' / ') ||
      '3D 机房仿真',
    deviceTotal,
    danger,
    fault,
    occupied,
    total,
    avgUtil:
      occupied === 0
        ? 0
        : Math.round(racks.reduce((s, r) => s + (r.utilization || 0), 0) / occupied),
    rackCount: occupied,
  })
}

function clearCss2dLabels(root?: THREE.Object3D | null) {
  if (root) {
    root.traverse((child) => {
      const label = child as CSS2DObject
      if (label.isCSS2DObject && label.element) {
        label.element.remove()
      }
    })
  }
  // 彻底清空标签层 DOM，避免旋转/重建残影
  if (labelRenderer?.domElement) {
    labelRenderer.domElement.replaceChildren()
  }
  document
    .querySelectorAll(
      '.webgl-rack-label, .webgl-pdu-label, .webgl-fixed-label, .webgl-label-input, .webgl-rack-screen',
    )
    .forEach((n) => n.remove())
}

function disposeObject(obj: THREE.Object3D) {
  obj.traverse((child) => {
    const mesh = child as THREE.Mesh
    if (mesh.geometry) mesh.geometry.dispose()
    const mat = mesh.material
    if (Array.isArray(mat)) mat.forEach((m) => m.dispose())
    else if (mat) mat.dispose()
  })
}

function clearRoom() {
  if (!roomGroup || !scene) {
    clearCss2dLabels(null)
    rackMeshes.clear()
    fixedMeshes.clear()
    cellGroups.clear()
    cellPickTargets.length = 0
    labelNodes.clear()
    labelObjects.clear()
    hoverMesh = null
    selectionMesh = null
    hoverKey = ''
    return
  }
  clearCss2dLabels(roomGroup)
  scene.remove(roomGroup)
  disposeObject(roomGroup)
  roomGroup = null
  rackMeshes.clear()
  fixedMeshes.clear()
  cellGroups.clear()
  cellPickTargets.length = 0
  labelNodes.clear()
  labelObjects.clear()
  hoverMesh = null
  selectionMesh = null
  hoverKey = ''
}

function labelVisibleForRow(row: number): boolean {
  if (rackDialogVisible.value) return false
  if (labelVisMode.value === 'hide_all') return false
  if (labelVisMode.value === 'all') return true
  const focus = Number(labelFocusRow.value) || 1
  if (labelVisMode.value === 'row_only') return row === focus
  if (labelVisMode.value === 'row_hide') return row !== focus
  return true
}

function applyLabelVisibility() {
  for (const [key, label] of labelObjects) {
    const el = labelNodes.get(key)
    const row = Number(el?.dataset.row || label.userData?.row || 0)
    const show = labelVisibleForRow(row)
    label.visible = show
    if (el) {
      el.style.visibility = show ? '' : 'hidden'
      el.classList.toggle('is-hidden', !show)
    }
  }
  if (labelRenderer) {
    labelRenderer.domElement.style.visibility =
      labelVisMode.value === 'hide_all' || rackDialogVisible.value ? 'hidden' : 'visible'
  }
}

function setLabelsHidden(hidden: boolean) {
  if (hidden) {
    if (labelRenderer) labelRenderer.domElement.style.visibility = 'hidden'
    for (const [, label] of labelObjects) label.visible = false
    document
      .querySelectorAll('.webgl-rack-label, .webgl-pdu-label, .webgl-fixed-label, .webgl-label-input')
      .forEach((el) => {
      const html = el as HTMLElement
      html.style.visibility = 'hidden'
      html.classList.add('is-hidden')
    })
  } else {
    applyLabelVisibility()
  }
}

function labelOffsetForSide(): THREE.Vector3 {
  // 编号固定在机柜顶面正中上方
  return new THREE.Vector3(0, RACK_H + 0.14, 0)
}

function makeRackLabel(
  code: string,
  key: string,
  row: number,
  col: number,
  muted = false,
  rackId?: string,
): CSS2DObject {
  const el = document.createElement('div')
  el.className = muted ? 'webgl-rack-label muted' : 'webgl-rack-label'
  el.textContent = code
  el.title = '双击查看机柜内部布局'
  el.dataset.row = String(row)
  el.dataset.col = String(col)
  if (rackId) el.dataset.rackId = rackId
  el.addEventListener('dblclick', (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (sceneEditMode.value || rackDialogVisible.value) return
    if (!rackId) {
      ElMessage.info('该机柜位尚未关联实体机柜')
      return
    }
    const rack = layout.value?.racks.find((r) => r.id === rackId) || null
    if (!rack) {
      ElMessage.info('未找到机柜数据')
      return
    }
    selectRack(rack)
    void openRackDialog(rack)
  })
  const label = new CSS2DObject(el)
  label.userData.row = row
  label.userData.col = col
  const show = labelVisibleForRow(row)
  label.visible = show
  if (!show) {
    el.style.visibility = 'hidden'
    el.classList.add('is-hidden')
  }
  labelNodes.set(key, el)
  labelObjects.set(key, label)
  return label
}

function attachRackCodeLabel(
  g: THREE.Group,
  code: string,
  key: string,
  row: number,
  col: number,
  rackId?: string,
  muted = false,
) {
  const label = makeRackLabel(code, key, row, col, muted, rackId)
  label.position.copy(labelOffsetForSide())
  g.add(label)
}

function makeRackMesh(rack: RoomMonitorRack, code: string, row: number, col: number): THREE.Group {
  const g = new THREE.Group()
  g.name = `rack:${rack.id}`
  g.userData.rackId = rack.id
  g.userData.cellType = 'rack'
  g.userData.row = row
  g.userData.col = col

  const bodyMat = new THREE.MeshStandardMaterial({
    color: 0x2b2d31,
    metalness: 0.35,
    roughness: 0.55,
  })
  const body = new THREE.Mesh(new THREE.BoxGeometry(RACK_W, RACK_H, RACK_D), bodyMat)
  body.position.y = RACK_H / 2
  body.castShadow = true
  body.receiveShadow = true
  body.userData.rackId = rack.id
  body.userData.cellType = 'rack'
  body.userData.row = row
  body.userData.col = col
  g.add(body)

  const doorColor = utilColor(rack.utilization, rack.status)
  const doorMat = new THREE.MeshStandardMaterial({
    color: doorColor,
    metalness: 0.2,
    roughness: 0.35,
    transparent: true,
    opacity: 0.55,
    emissive: doorColor,
    emissiveIntensity: 0.18,
  })
  const door = new THREE.Mesh(new THREE.BoxGeometry(RACK_W * 0.82, RACK_H * 0.88, 0.04), doorMat)
  door.position.set(0, RACK_H / 2, RACK_D / 2 + 0.01)
  door.userData.rackId = rack.id
  door.userData.cellType = 'rack'
  door.userData.row = row
  door.userData.col = col
  g.add(door)

  const barMat = new THREE.MeshStandardMaterial({ color: 0x1a1c20, metalness: 0.1, roughness: 0.7 })
  for (let i = 0; i < 12; i++) {
    const bar = new THREE.Mesh(new THREE.BoxGeometry(RACK_W * 0.72, 0.02, 0.02), barMat)
    bar.position.set(0, 0.25 + i * 0.14, RACK_D / 2 + 0.035)
    bar.userData.rackId = rack.id
    bar.userData.cellType = 'rack'
    bar.userData.row = row
    bar.userData.col = col
    g.add(bar)
  }

  const led = new THREE.Mesh(
    new THREE.BoxGeometry(0.04, 0.04, 0.02),
    new THREE.MeshStandardMaterial({
      color: doorColor,
      emissive: doorColor,
      emissiveIntensity: 0.9,
    }),
  )
  led.position.set(RACK_W * 0.28, RACK_H - 0.18, RACK_D / 2 + 0.04)
  led.userData.rackId = rack.id
  led.userData.cellType = 'rack'
  led.userData.row = row
  led.userData.col = col
  g.add(led)

  attachRackCodeLabel(g, code, rack.id, row, col, rack.id, false)

  if ((rack.utilization || 0) >= 85) {
    const alarm = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.12, 0),
      new THREE.MeshStandardMaterial({
        color: 0xe53935,
        emissive: 0xe53935,
        emissiveIntensity: 0.7,
      }),
    )
    alarm.position.set(0, RACK_H + 0.35, -0.15)
    alarm.userData.rackId = rack.id
    alarm.userData.cellType = 'rack'
    g.add(alarm)
  }

  addCellPickVolume(g, 'rack', row, col)
  g.userData.rackId = rack.id

  g.traverse((child) => {
    if (!child.userData.cellType) {
      child.userData.cellType = 'rack'
      child.userData.row = row
      child.userData.col = col
      child.userData.rackId = rack.id
    }
  })

  return g
}

/** 机柜位占位（尚无物理机柜）：与实体机柜同款深灰机身 + 蓝门，便于满柜恢复后视觉一致 */
function buildPlaceholderRack(code: string, row: number, col: number): THREE.Group {
  const g = new THREE.Group()
  g.userData.cellType = 'rack'
  g.userData.row = row
  g.userData.col = col

  const bodyMat = new THREE.MeshStandardMaterial({
    color: 0x2b2d31,
    metalness: 0.35,
    roughness: 0.55,
  })
  const body = new THREE.Mesh(new THREE.BoxGeometry(RACK_W, RACK_H, RACK_D), bodyMat)
  body.position.y = RACK_H / 2
  body.castShadow = true
  body.receiveShadow = true
  g.add(body)

  const doorColor = 0x3aa0ff
  const doorMat = new THREE.MeshStandardMaterial({
    color: doorColor,
    metalness: 0.2,
    roughness: 0.35,
    transparent: true,
    opacity: 0.55,
    emissive: doorColor,
    emissiveIntensity: 0.18,
  })
  const door = new THREE.Mesh(new THREE.BoxGeometry(RACK_W * 0.82, RACK_H * 0.88, 0.04), doorMat)
  door.position.set(0, RACK_H / 2, RACK_D / 2 + 0.01)
  g.add(door)

  const barMat = new THREE.MeshStandardMaterial({ color: 0x1a1c20, metalness: 0.1, roughness: 0.7 })
  for (let i = 0; i < 12; i++) {
    const bar = new THREE.Mesh(new THREE.BoxGeometry(RACK_W * 0.72, 0.02, 0.02), barMat)
    bar.position.set(0, 0.25 + i * 0.14, RACK_D / 2 + 0.035)
    g.add(bar)
  }

  const led = new THREE.Mesh(
    new THREE.BoxGeometry(0.04, 0.04, 0.02),
    new THREE.MeshStandardMaterial({
      color: doorColor,
      emissive: doorColor,
      emissiveIntensity: 0.9,
    }),
  )
  led.position.set(RACK_W * 0.28, RACK_H - 0.18, RACK_D / 2 + 0.04)
  g.add(led)

  attachRackCodeLabel(g, code, `empty:${row}-${col}`, row, col, undefined, false)
  addCellPickVolume(g, 'rack', row, col)

  g.traverse((child) => {
    if (!child.userData.cellType) {
      child.userData.cellType = 'rack'
      child.userData.row = row
      child.userData.col = col
    }
  })
  return g
}

/** 不可见加高拾取盒，提升单格点击命中率与辨识 */
function addCellPickVolume(
  g: THREE.Group,
  cellType: string,
  row: number,
  col: number,
  height = RACK_H,
) {
  const hit = new THREE.Mesh(
    new THREE.BoxGeometry(RACK_W + GAP * 0.85, height, RACK_D + 0.2),
    new THREE.MeshBasicMaterial({ visible: false }),
  )
  hit.position.y = height / 2
  hit.userData.cellType = cellType
  hit.userData.row = row
  hit.userData.col = col
  hit.userData.isPickVolume = true
  g.add(hit)
}

function buildEmptyPad(code: string, row: number, col: number): THREE.Group {
  const g = new THREE.Group()
  g.userData.cellType = 'empty'
  g.userData.row = row
  g.userData.col = col

  const mat = new THREE.MeshStandardMaterial({
    color: 0xb8cce0,
    transparent: true,
    opacity: 0.55,
    roughness: 1,
  })
  const box = new THREE.Mesh(new THREE.BoxGeometry(RACK_W * 0.92, 0.05, RACK_D * 0.92), mat)
  box.position.y = 0.025
  g.add(box)

  // 半高虚框，便于看见可点格子
  const frame = new THREE.Mesh(
    new THREE.BoxGeometry(RACK_W * 0.88, RACK_H * 0.35, RACK_D * 0.88),
    new THREE.MeshStandardMaterial({
      color: 0x9eb6cc,
      transparent: true,
      opacity: 0.18,
      depthWrite: false,
    }),
  )
  frame.position.y = RACK_H * 0.18
  g.add(frame)

  const label = makeRackLabel(code, `pad:${row}-${col}`, row, col, true)
  label.position.copy(labelOffsetForSide())
  g.add(label)

  addCellPickVolume(g, 'empty', row, col, RACK_H * 0.55)

  g.traverse((child) => {
    if (!child.userData.cellType) {
      child.userData.cellType = 'empty'
      child.userData.row = row
      child.userData.col = col
    }
  })
  return g
}

function buildPillarMesh(
  row: number,
  col: number,
  selected: boolean,
  shape: 'square' | 'round' = 'square',
): THREE.Group {
  const kind: CellKind = shape === 'round' ? 'pillar_round' : 'pillar'
  const g = new THREE.Group()
  g.name = `${kind}:${row}-${col}`
  g.userData.cellType = kind
  g.userData.row = row
  g.userData.col = col

  const bodyColor = selected ? 0x3aa0ff : 0x8494a6
  const topColor = selected ? 0x5ab0ff : 0x9aa8b8
  const bottomColor = selected ? 0x2a7fd0 : 0x6a7c90

  // 加粗立柱：方形边长 / 圆形直径约 0.32（约半个机柜宽）
  const thickness = 0.32
  const postH = RACK_H * 0.98
  const radialSegs = 24

  const bodyMat = new THREE.MeshStandardMaterial({
    color: bodyColor,
    metalness: 0.28,
    roughness: 0.42,
    emissive: selected ? 0x1a6fd0 : 0x000000,
    emissiveIntensity: selected ? 0.35 : 0,
  })
  const post =
    shape === 'round'
      ? new THREE.Mesh(new THREE.CylinderGeometry(thickness / 2, thickness / 2, postH, radialSegs), bodyMat)
      : new THREE.Mesh(new THREE.BoxGeometry(thickness, postH, thickness), bodyMat)
  post.position.y = postH / 2
  post.castShadow = true
  post.receiveShadow = true
  g.add(post)

  const capMat = new THREE.MeshStandardMaterial({
    color: topColor,
    metalness: 0.2,
    roughness: 0.5,
    emissive: selected ? 0x1a6fd0 : 0x000000,
    emissiveIntensity: selected ? 0.2 : 0,
  })
  const cap =
    shape === 'round'
      ? new THREE.Mesh(new THREE.CylinderGeometry(thickness * 0.58, thickness * 0.58, 0.07, radialSegs), capMat)
      : new THREE.Mesh(new THREE.BoxGeometry(thickness * 1.14, 0.07, thickness * 1.14), capMat)
  cap.position.y = postH + 0.02
  cap.castShadow = true
  g.add(cap)

  const baseMat = new THREE.MeshStandardMaterial({
    color: bottomColor,
    metalness: 0.22,
    roughness: 0.55,
    emissive: selected ? 0x1a6fd0 : 0x000000,
    emissiveIntensity: selected ? 0.15 : 0,
  })
  const base =
    shape === 'round'
      ? new THREE.Mesh(new THREE.CylinderGeometry(thickness * 0.72, thickness * 0.72, 0.1, radialSegs), baseMat)
      : new THREE.Mesh(new THREE.BoxGeometry(thickness * 1.38, 0.1, thickness * 1.38), baseMat)
  base.position.y = 0.05
  base.castShadow = true
  base.receiveShadow = true
  g.add(base)

  addCellPickVolume(g, kind, row, col)

  g.traverse((child) => {
    if (!child.userData.cellType) {
      child.userData.cellType = kind
      child.userData.row = row
      child.userData.col = col
    }
  })

  return g
}

function parseHexColor(hex: string | undefined, fallback: number): number {
  if (!hex) return fallback
  const raw = hex.trim().replace('#', '')
  if (!/^[0-9a-fA-F]{6}$/.test(raw)) return fallback
  return Number.parseInt(raw, 16)
}

function attachFixedLabel(
  g: THREE.Group,
  text: string,
  key: string,
  row: number,
  col: number,
  kind: CellKind,
  y: number,
) {
  const el = document.createElement('div')
  el.className = kind === 'pdu' ? 'webgl-pdu-label' : 'webgl-fixed-label'
  el.dataset.kind = kind
  el.textContent = text
  el.dataset.row = String(row)
  el.dataset.col = String(col)
  const label = new CSS2DObject(el)
  label.userData.row = row
  label.userData.col = col
  label.position.copy(labelOffsetForSide())
  label.position.y = y
  const show = labelVisibleForRow(row)
  label.visible = show
  if (!show) {
    el.style.visibility = 'hidden'
    el.classList.add('is-hidden')
  }
  g.add(label)
  labelNodes.set(key, el)
  labelObjects.set(key, label)
}

function buildCabinetLikeMesh(
  kind: 'power' | 'ac' | 'custom' | 'pdu' | 'odf',
  row: number,
  col: number,
  selected: boolean,
  opts?: { label?: string; color?: string; heightRatio?: number },
): THREE.Group {
  const g = new THREE.Group()
  g.name = `${kind}:${row}-${col}`
  g.userData.cellType = kind
  g.userData.row = row
  g.userData.col = col

  const h = RACK_H * (opts?.heightRatio ?? (kind === 'pdu' ? 0.7 : 1))
  const baseColor =
    kind === 'power'
      ? 0x3a3f48
      : kind === 'ac'
        ? 0x3a5568
        : kind === 'odf'
          ? 0x2f3540
          : kind === 'custom'
            ? parseHexColor(opts?.color, 0x5a7a9a)
            : 0x2a303c
  const bodyColor = selected ? 0x3d5a78 : baseColor

  const body = new THREE.Mesh(
    new THREE.BoxGeometry(RACK_W, h, RACK_D),
    new THREE.MeshStandardMaterial({
      color: bodyColor,
      metalness: 0.38,
      roughness: 0.48,
      emissive: selected ? 0x1a6fd0 : 0x000000,
      emissiveIntensity: selected ? 0.25 : 0,
    }),
  )
  body.position.y = h / 2
  body.castShadow = true
  body.receiveShadow = true
  g.add(body)

  if (kind === 'power') {
    const stripe = new THREE.Mesh(
      new THREE.BoxGeometry(RACK_W * 0.92, 0.1, 0.03),
      new THREE.MeshStandardMaterial({
        color: 0xf5c542,
        emissive: 0xf5c542,
        emissiveIntensity: 0.28,
        metalness: 0.15,
        roughness: 0.45,
      }),
    )
    stripe.position.set(0, h * 0.78, RACK_D / 2 + 0.02)
    g.add(stripe)
    const warn = new THREE.Mesh(
      new THREE.BoxGeometry(0.16, 0.16, 0.03),
      new THREE.MeshStandardMaterial({ color: 0xf0a020, metalness: 0.2, roughness: 0.4 }),
    )
    warn.position.set(0, h * 0.5, RACK_D / 2 + 0.02)
    g.add(warn)
  } else if (kind === 'ac') {
    const ventMat = new THREE.MeshStandardMaterial({
      color: 0x8eb6d0,
      metalness: 0.25,
      roughness: 0.55,
    })
    for (let i = 0; i < 5; i++) {
      const vent = new THREE.Mesh(new THREE.BoxGeometry(RACK_W * 0.72, 0.04, 0.02), ventMat)
      vent.position.set(0, h * (0.28 + i * 0.12), RACK_D / 2 + 0.02)
      g.add(vent)
    }
    const badge = new THREE.Mesh(
      new THREE.BoxGeometry(RACK_W * 0.35, 0.08, 0.03),
      new THREE.MeshStandardMaterial({
        color: 0x3aa0ff,
        emissive: 0x3aa0ff,
        emissiveIntensity: 0.2,
      }),
    )
    badge.position.set(0, h * 0.88, RACK_D / 2 + 0.02)
    g.add(badge)
  } else if (kind === 'odf') {
    // 光纤配线架：正面多排适配器面板（黄/橙光纤标识色）
    const panelMat = new THREE.MeshStandardMaterial({
      color: 0x1e2430,
      metalness: 0.35,
      roughness: 0.45,
    })
    const panel = new THREE.Mesh(new THREE.BoxGeometry(RACK_W * 0.88, h * 0.72, 0.04), panelMat)
    panel.position.set(0, h * 0.48, RACK_D / 2 + 0.01)
    g.add(panel)

    const portMat = new THREE.MeshStandardMaterial({
      color: 0xf0b429,
      emissive: 0xf0b429,
      emissiveIntensity: 0.18,
      metalness: 0.15,
      roughness: 0.4,
    })
    const cols = 6
    const rows = 8
    const portW = RACK_W * 0.1
    const portH = 0.045
    const startX = -((cols - 1) * portW * 1.15) / 2
    const startY = h * 0.22
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const port = new THREE.Mesh(new THREE.BoxGeometry(portW * 0.85, portH, 0.03), portMat)
        port.position.set(
          startX + c * portW * 1.15,
          startY + r * (portH + 0.035),
          RACK_D / 2 + 0.04,
        )
        g.add(port)
      }
    }
    const badge = new THREE.Mesh(
      new THREE.BoxGeometry(RACK_W * 0.42, 0.08, 0.03),
      new THREE.MeshStandardMaterial({
        color: 0xe8a317,
        emissive: 0xe8a317,
        emissiveIntensity: 0.22,
      }),
    )
    badge.position.set(0, h * 0.9, RACK_D / 2 + 0.02)
    g.add(badge)
  } else if (kind === 'custom') {
    const accent = new THREE.Mesh(
      new THREE.BoxGeometry(RACK_W * 0.9, 0.08, 0.03),
      new THREE.MeshStandardMaterial({
        color: parseHexColor(opts?.color, 0x5a7a9a),
        emissive: parseHexColor(opts?.color, 0x5a7a9a),
        emissiveIntensity: 0.22,
      }),
    )
    accent.position.set(0, h * 0.82, RACK_D / 2 + 0.02)
    g.add(accent)
  } else {
    const stripe = new THREE.Mesh(
      new THREE.BoxGeometry(RACK_W * 0.92, 0.08, 0.03),
      new THREE.MeshStandardMaterial({
        color: 0xf59e0b,
        emissive: 0xf59e0b,
        emissiveIntensity: 0.35,
        metalness: 0.2,
        roughness: 0.4,
      }),
    )
    stripe.position.set(0, h * 0.72, RACK_D / 2 + 0.02)
    g.add(stripe)
  }

  const labelText =
    (opts?.label || '').trim() ||
    (kind === 'power'
      ? '电柜'
      : kind === 'ac'
        ? '空调'
        : kind === 'odf'
          ? 'ODF'
          : kind === 'custom'
            ? '自定义'
            : '列头')
  attachFixedLabel(g, labelText, `${kind}:${row}-${col}`, row, col, kind, h + 0.12)
  addCellPickVolume(g, kind, row, col, h)

  g.traverse((child) => {
    if (!child.userData.cellType) {
      child.userData.cellType = kind
      child.userData.row = row
      child.userData.col = col
    }
  })

  return g
}

function buildPduMesh(row: number, col: number, selected: boolean): THREE.Group {
  return buildCabinetLikeMesh('pdu', row, col, selected, { label: '列头', heightRatio: 0.7 })
}

function buildPowerMesh(row: number, col: number, selected: boolean): THREE.Group {
  return buildCabinetLikeMesh('power', row, col, selected, { label: '电柜', heightRatio: 0.88 })
}

function buildAcMesh(row: number, col: number, selected: boolean): THREE.Group {
  return buildCabinetLikeMesh('ac', row, col, selected, { label: '空调', heightRatio: 0.9 })
}

function buildOdfMesh(row: number, col: number, selected: boolean): THREE.Group {
  return buildCabinetLikeMesh('odf', row, col, selected, { label: 'ODF', heightRatio: 1 })
}

function buildCustomMesh(
  row: number,
  col: number,
  selected: boolean,
  prop?: CellProp,
): THREE.Group {
  return buildCabinetLikeMesh('custom', row, col, selected, {
    label: prop?.label || '自定义',
    color: prop?.color || '#5a7a9a',
    heightRatio: 1,
  })
}

function setFixedSelectedStyle(group: THREE.Object3D, kind: CellKind, selected: boolean) {
  if (isPillarKind(kind)) {
    const color = selected ? 0x3aa0ff : 0x8494a6
    const emissive = selected ? 0x1a6fd0 : 0x000000
    group.traverse((child) => {
      const mesh = child as THREE.Mesh
      if (!mesh.isMesh) return
      const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
      for (const m of mats) {
        const std = m as THREE.MeshStandardMaterial
        if (!std?.isMeshStandardMaterial) continue
        std.color.setHex(color)
        std.emissive.setHex(emissive)
        std.emissiveIntensity = selected ? 0.35 : 0
      }
    })
    return
  }
  if (isFixedKind(kind)) {
    group.traverse((child) => {
      const mesh = child as THREE.Mesh
      if (!mesh.isMesh) return
      if (mesh.userData.isPickVolume) return
      const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
      for (const m of mats) {
        const std = m as THREE.MeshStandardMaterial
        if (!std?.isMeshStandardMaterial) continue
        const hex = std.color.getHex()
        // 保留装饰色条
        if (
          hex === 0xf59e0b ||
          hex === 0xf5c542 ||
          hex === 0xf0a020 ||
          hex === 0xf0b429 ||
          hex === 0xe8a317 ||
          hex === 0x8eb6d0 ||
          hex === 0x3aa0ff
        ) {
          continue
        }
        if (selected) {
          std.emissive.setHex(0x1a6fd0)
          std.emissiveIntensity = 0.28
        } else {
          std.emissive.setHex(0x000000)
          std.emissiveIntensity = 0
        }
      }
    })
  }
}

function cellKey(row: number, col: number) {
  return `${row}:${col}`
}

function setGroupEmissiveHighlight(group: THREE.Object3D, selected: boolean, kind: CellKind) {
  group.traverse((child) => {
    const mesh = child as THREE.Mesh
    if (!mesh.isMesh) return
    if (mesh.userData.isPickVolume || mesh.userData.isHighlightFrame) return
    const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
    for (const m of mats) {
      const std = m as THREE.MeshStandardMaterial
      if (!std?.isMeshStandardMaterial || !std.emissive) continue
      if (selected) {
        if (std.userData.baseEmissiveIntensity == null) {
          std.userData.baseEmissiveIntensity = std.emissiveIntensity
          std.userData.baseEmissiveHex = std.emissive.getHex()
        }
        if (kind === 'rack') {
          std.emissive.setHex(0x3aa0ff)
          std.emissiveIntensity = Math.max(std.emissiveIntensity, 0.45)
        } else {
          std.emissive.setHex(0x1a6fd0)
          std.emissiveIntensity = 0.35
        }
      } else if (std.userData.baseEmissiveIntensity != null) {
        std.emissive.setHex(std.userData.baseEmissiveHex ?? 0x000000)
        std.emissiveIntensity = std.userData.baseEmissiveIntensity
        delete std.userData.baseEmissiveIntensity
        delete std.userData.baseEmissiveHex
      }
    }
  })
}

function ensureSelectionMesh() {
  if (selectionMesh || !roomGroup) return
  selectionMesh = new THREE.Mesh(
    new THREE.BoxGeometry(RACK_W + 0.12, RACK_H + 0.14, RACK_D + 0.14),
    new THREE.MeshBasicMaterial({
      color: 0xf5a623,
      transparent: true,
      opacity: 0.28,
      depthWrite: false,
    }),
  )
  selectionMesh.visible = false
  selectionMesh.renderOrder = 3
  selectionMesh.userData.isHighlightFrame = true
  roomGroup.add(selectionMesh)
}

function refreshCellSelection() {
  const sel = selectedCell.value
  refreshFixedSelection()

  for (const [key, group] of cellGroups) {
    const [rStr, cStr] = key.split(':')
    const row = Number(rStr)
    const col = Number(cStr)
    const isSel = !!sel && sel.row === row && sel.col === col
    const kind = (group.userData.cellType as CellKind) || sel?.kind || 'rack'
    setGroupEmissiveHighlight(group, isSel, isSel ? sel!.kind : kind)
  }

  if (!gridMeta || !roomGroup) {
    if (selectionMesh) selectionMesh.visible = false
    return
  }
  ensureSelectionMesh()
  if (!selectionMesh) return
  if (!sel) {
    selectionMesh.visible = false
    return
  }
  selectionMesh.visible = true
  selectionMesh.position.set(
    gridMeta.startX + (sel.col - 1) * gridMeta.pitchX,
    RACK_H / 2,
    gridMeta.startZ + (sel.row - 1) * gridMeta.pitchZ,
  )
  const mat = selectionMesh.material as THREE.MeshBasicMaterial
  mat.color.setHex(sel.kind === 'rack' ? 0x3aa0ff : 0xf5a623)
  mat.opacity = sel.kind === 'rack' ? 0.32 : 0.26
}

function refreshFixedSelection() {
  const sel = selectedCell.value
  for (const [key, mesh] of fixedMeshes) {
    const [kind, rStr, cStr] = key.split(':')
    const row = Number(rStr)
    const col = Number(cStr)
    const isSel = !!sel && sel.row === row && sel.col === col && sel.kind === kind
    setFixedSelectedStyle(mesh, kind as CellKind, isSel)
  }
}

function selectFixed(row: number, col: number, kind: CellKind) {
  selectedCell.value = { row, col, kind }
  selectedRackId.value = null
  refreshCellSelection()
}

function buildSceneContent(data: RoomMonitorLayout, resetCameraPose = false) {
  if (!scene) return
  const sl = sceneLayout.value
  if (!sl) return

  clearRoom()
  roomGroup = new THREE.Group()

  const rows = sl.rows
  const cols = sl.cols
  const roomW = cols * (RACK_W + GAP) + 3.2
  const roomD = rows * (RACK_D + AISLE) + 2.8
  const wallH = 3.2
  const startX = -((cols - 1) * (RACK_W + GAP)) / 2
  const startZ = -roomD / 2 + 1.4

  gridMeta = {
    startX,
    startZ,
    cols,
    rows,
    pitchX: RACK_W + GAP,
    pitchZ: RACK_D + AISLE,
    roomW,
    roomD,
  }

  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(roomW, roomD),
    new THREE.MeshStandardMaterial({ color: 0xe8eef5, roughness: 0.92, metalness: 0.05 }),
  )
  floor.rotation.x = -Math.PI / 2
  floor.receiveShadow = true
  roomGroup.add(floor)

  const grid = new THREE.GridHelper(
    Math.max(roomW, roomD),
    Math.ceil(Math.max(roomW, roomD) * 2),
    0xb8c4d0,
    0xd0d8e2,
  )
  grid.position.y = 0.01
  roomGroup.add(grid)

  const wallMat = new THREE.MeshPhysicalMaterial({
    color: 0xb8d4f0,
    transparent: true,
    opacity: 0.14,
    metalness: 0.05,
    roughness: 0.12,
    transmission: 0.82,
    thickness: 0.35,
    side: THREE.DoubleSide,
    depthWrite: false,
  })
  const walls: Array<[number, number, number, number, number, number]> = [
    [roomW, wallH, 0.06, 0, wallH / 2, -roomD / 2],
    [roomW, wallH, 0.06, 0, wallH / 2, roomD / 2],
    [0.06, wallH, roomD, -roomW / 2, wallH / 2, 0],
    [0.06, wallH, roomD, roomW / 2, wallH / 2, 0],
  ]
  for (const [w, h, d, x, y, z] of walls) {
    const wall = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), wallMat)
    wall.position.set(x, y, z)
    wall.renderOrder = 1
    roomGroup.add(wall)
  }

  const cornerMat = new THREE.MeshStandardMaterial({
    color: 0x6a7c90,
    metalness: 0.25,
    roughness: 0.45,
  })
  const pillarSize = 0.14
  const corners: Array<[number, number]> = [
    [-roomW / 2, -roomD / 2],
    [roomW / 2, -roomD / 2],
    [-roomW / 2, roomD / 2],
    [roomW / 2, roomD / 2],
  ]
  for (const [cx, cz] of corners) {
    const corner = new THREE.Mesh(new THREE.BoxGeometry(pillarSize, wallH, pillarSize), cornerMat)
    corner.position.set(cx, wallH / 2, cz)
    corner.castShadow = true
    roomGroup.add(corner)
  }

  const railMat = new THREE.MeshStandardMaterial({ color: 0x8aa0b5, metalness: 0.3, roughness: 0.4 })
  const rails: Array<[number, number, number, number, number, number]> = [
    [roomW, 0.05, 0.05, 0, wallH - 0.02, -roomD / 2],
    [roomW, 0.05, 0.05, 0, wallH - 0.02, roomD / 2],
    [0.05, 0.05, roomD, -roomW / 2, wallH - 0.02, 0],
    [0.05, 0.05, roomD, roomW / 2, wallH - 0.02, 0],
  ]
  for (const [w, h, d, x, y, z] of rails) {
    const rail = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), railMat)
    rail.position.set(x, y, z)
    roomGroup.add(rail)
  }

  const trayMat = new THREE.MeshStandardMaterial({ color: 0x6b7785, metalness: 0.55, roughness: 0.4 })
  for (let i = 0; i < rows; i++) {
    const z = startZ + i * (RACK_D + AISLE) + RACK_D / 2
    const tray = new THREE.Mesh(new THREE.BoxGeometry(roomW - 1.2, 0.06, 0.28), trayMat)
    tray.position.set(0, wallH - 0.45, z)
    roomGroup.add(tray)
  }

  const ventMat = new THREE.MeshStandardMaterial({ color: 0x8a939e, roughness: 0.7 })
  const codes = data.slot_codes || []
  const sel = selectedCell.value

  for (let row = 1; row <= rows; row++) {
    const rowIdx = row - 1
    const z = startZ + rowIdx * (RACK_D + AISLE)
    const vent = new THREE.Mesh(
      new THREE.BoxGeometry(cols * (RACK_W + GAP), 0.03, 0.55),
      ventMat,
    )
    vent.position.set(0, 0.02, z + RACK_D / 2 + 0.45)
    roomGroup.add(vent)

    const rowRacks = data.racks
      .filter((r) => r.row_no === row)
      .sort((a, b) => a.column_no - b.column_no)
    const plans = planSceneRow(sl, row)

    for (const plan of plans) {
      const x = startX + (plan.col - 1) * (RACK_W + GAP)
      const code =
        codes[rowIdx]?.[plan.col - 1] ||
        `R${String(row).padStart(2, '0')}${String(plan.col).padStart(2, '0')}`

      if (plan.kind === 'rack') {
        const rack = rowRacks[plan.rackIndex ?? -1]
        // 严格优先场景 slot_codes（编号方向改的是格子码，不能被 rack.code 盖住）
        const slotCode = (codes[rowIdx]?.[plan.col - 1] || '').trim()
        const displayCode = slotCode || (rack?.code || '').trim() || code
        if (rack) {
          const mesh = makeRackMesh(rack, displayCode, row, plan.col)
          mesh.position.set(x, 0, z)
          roomGroup.add(mesh)
          rackMeshes.set(rack.id, mesh)
          cellGroups.set(cellKey(row, plan.col), mesh)
          cellPickTargets.push(mesh)
        } else {
          const empty = buildPlaceholderRack(displayCode, row, plan.col)
          empty.position.set(x, 0, z)
          roomGroup.add(empty)
          cellGroups.set(cellKey(row, plan.col), empty)
          cellPickTargets.push(empty)
        }
      } else if (plan.kind === 'pillar' || plan.kind === 'pillar_round') {
        const isSel =
          !!sel &&
          sel.row === row &&
          sel.col === plan.col &&
          (sel.kind === 'pillar' || sel.kind === 'pillar_round') &&
          sel.kind === plan.kind
        const pillar = buildPillarMesh(
          row,
          plan.col,
          isSel,
          plan.kind === 'pillar_round' ? 'round' : 'square',
        )
        pillar.position.set(x, 0, z)
        roomGroup.add(pillar)
        fixedMeshes.set(`${plan.kind}:${row}:${plan.col}`, pillar)
        cellGroups.set(cellKey(row, plan.col), pillar)
        cellPickTargets.push(pillar)
      } else if (plan.kind === 'pdu') {
        const isSel = !!sel && sel.row === row && sel.col === plan.col && sel.kind === 'pdu'
        const pdu = buildPduMesh(row, plan.col, isSel)
        pdu.position.set(x, 0, z)
        roomGroup.add(pdu)
        fixedMeshes.set(`pdu:${row}:${plan.col}`, pdu)
        cellGroups.set(cellKey(row, plan.col), pdu)
        cellPickTargets.push(pdu)
      } else if (plan.kind === 'power') {
        const isSel = !!sel && sel.row === row && sel.col === plan.col && sel.kind === 'power'
        const mesh = buildPowerMesh(row, plan.col, isSel)
        mesh.position.set(x, 0, z)
        roomGroup.add(mesh)
        fixedMeshes.set(`power:${row}:${plan.col}`, mesh)
        cellGroups.set(cellKey(row, plan.col), mesh)
        cellPickTargets.push(mesh)
      } else if (plan.kind === 'ac') {
        const isSel = !!sel && sel.row === row && sel.col === plan.col && sel.kind === 'ac'
        const mesh = buildAcMesh(row, plan.col, isSel)
        mesh.position.set(x, 0, z)
        roomGroup.add(mesh)
        fixedMeshes.set(`ac:${row}:${plan.col}`, mesh)
        cellGroups.set(cellKey(row, plan.col), mesh)
        cellPickTargets.push(mesh)
      } else if (plan.kind === 'odf') {
        const isSel = !!sel && sel.row === row && sel.col === plan.col && sel.kind === 'odf'
        const mesh = buildOdfMesh(row, plan.col, isSel)
        mesh.position.set(x, 0, z)
        roomGroup.add(mesh)
        fixedMeshes.set(`odf:${row}:${plan.col}`, mesh)
        cellGroups.set(cellKey(row, plan.col), mesh)
        cellPickTargets.push(mesh)
      } else if (plan.kind === 'custom') {
        const isSel = !!sel && sel.row === row && sel.col === plan.col && sel.kind === 'custom'
        const prop = getCellProp(sl, row, plan.col)
        const mesh = buildCustomMesh(row, plan.col, isSel, prop)
        mesh.position.set(x, 0, z)
        roomGroup.add(mesh)
        fixedMeshes.set(`custom:${row}:${plan.col}`, mesh)
        cellGroups.set(cellKey(row, plan.col), mesh)
        cellPickTargets.push(mesh)
      } else {
        const empty = buildEmptyPad(code, row, plan.col)
        empty.position.set(x, 0, z)
        roomGroup.add(empty)
        cellGroups.set(cellKey(row, plan.col), empty)
        cellPickTargets.push(empty)
      }
    }
  }

  scene.add(roomGroup)

  // 按机房尺度动态弱化雾化，避免远端过早发白、物体过小难辨
  if (scene) {
    const span = Math.max(roomW, roomD, 8)
    const fogNear = Math.max(32, span * 1.6)
    const fogFar = Math.max(95, span * 4.2)
    scene.fog = new THREE.Fog(0xd9e6f5, fogNear, fogFar)
  }

  if (camera && controls && resetCameraPose) {
    // 更近的默认机位，远端机柜更大更清晰
    const dist = Math.max(roomW, roomD) * 0.68
    camera.position.set(dist * 0.72, dist * 0.4, dist * 0.78)
    camera.far = Math.max(200, Math.max(roomW, roomD) * 8)
    camera.updateProjectionMatrix()
    controls.maxDistance = Math.max(55, Math.max(roomW, roomD) * 2.8)
    controls.target.set(0, 0.9, 0)
    controls.update()
  }

  if (rackDialogVisible.value) setLabelsHidden(true)
  else applyLabelVisibility()
  refreshCellSelection()
}

function scheduleRebuild(resetCameraPose = false) {
  if (!layout.value || !sceneLayout.value) return
  if (rebuildRaf) cancelAnimationFrame(rebuildRaf)
  rebuildRaf = requestAnimationFrame(() => {
    rebuildRaf = 0
    if (layout.value && sceneLayout.value) {
      buildSceneContent(layout.value, resetCameraPose)
    }
  })
}

function startInlineEdit(el: HTMLElement, row: number, col: number, current: string) {
  if (el.querySelector('input')) return
  const input = document.createElement('input')
  input.className = 'webgl-label-input'
  input.value = current
  input.maxLength = 50
  el.textContent = ''
  el.appendChild(input)
  input.focus()
  input.select()
  let settled = false
  const finish = (text: string) => {
    if (settled) return
    settled = true
    if (el.isConnected) el.textContent = text
  }
  const commit = async () => {
    if (settled) return
    const next = input.value.trim()
    if (!next || next === current) {
      finish(current)
      return
    }
    settled = true
    try {
      await saveSlotCode(row, col, next)
      ElMessage.success('标号已更新')
    } catch (e) {
      if (el.isConnected) el.textContent = current
      settled = false
      ElMessage.error(e instanceof Error ? e.message : '保存失败')
    }
  }
  input.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') {
      ev.preventDefault()
      input.blur()
      void commit()
    }
    if (ev.key === 'Escape') {
      finish(current)
    }
  })
  input.addEventListener('blur', () => {
    window.setTimeout(() => void commit(), 0)
  })
}

/** 仅按场景网格读取 slot_codes（不用 rack.column_no，避免右编号被旧柜码盖掉） */
function getSceneSlotCodesMatrix(): string[][] {
  const data = layout.value
  const sl = sceneLayout.value
  if (!data || !sl) return []
  const codes = data.slot_codes || []
  return Array.from({ length: sl.rows }, (_, ri) =>
    Array.from({ length: sl.cols }, (_, ci) => (codes[ri]?.[ci] || '').trim()),
  )
}

function cloneSlotCodes(): string[][] {
  const data = layout.value
  const sl = sceneLayout.value
  if (!data || !sl) return []
  const sceneCodes = getSceneSlotCodesMatrix()
  const rackMap = new Map(data.racks.map((r) => [`${r.row_no}-${r.column_no}`, r]))
  return Array.from({ length: sl.rows }, (_, ri) =>
    Array.from({ length: sl.cols }, (_, ci) => {
      const fromScene = sceneCodes[ri]?.[ci] || ''
      if (fromScene) return fromScene
      const rack = rackMap.get(`${ri + 1}-${ci + 1}`)
      return (rack?.code || '').trim()
    }),
  )
}

function cloneSlotCodeMatrix(codes: string[][] | undefined): string[][] {
  return (codes || []).map((row) => [...row])
}

function captureEditSnapshot(): EditSnapshot | null {
  if (!sceneLayout.value || !layout.value) return null
  return {
    scene: toPersistLayout(sceneLayout.value),
    slotCodes: cloneSlotCodeMatrix(layout.value.slot_codes),
    codePrefix: layout.value.code_prefix,
    labelSide: labelSide.value,
    editRows: editRows.value,
    editCols: editCols.value,
  }
}

function applyEditSnapshot(snap: EditSnapshot) {
  sceneLayout.value = snap.scene
  editRows.value = snap.editRows
  editCols.value = snap.editCols
  labelSide.value = snap.labelSide
  if (layout.value) {
    layout.value = {
      ...layout.value,
      slot_codes: cloneSlotCodeMatrix(snap.slotCodes),
      code_prefix: snap.codePrefix ?? layout.value.code_prefix,
    }
  }
  selectedCell.value = null
  selectedRackId.value = null
}

function snapshotEquals(a: EditSnapshot | null, b: EditSnapshot | null): boolean {
  if (!a || !b) return false
  return (
    JSON.stringify(a.scene) === JSON.stringify(b.scene) &&
    JSON.stringify(a.slotCodes) === JSON.stringify(b.slotCodes) &&
    a.labelSide === b.labelSide &&
    (a.codePrefix || '') === (b.codePrefix || '')
  )
}

function refreshDirtyFromBaseline() {
  const current = captureEditSnapshot()
  dirty.value = !snapshotEquals(current, editBaseline)
}

/** 在变更前压入撤销栈（编辑模式内） */
function pushUndoSnapshot() {
  if (!sceneEditMode.value) return
  const snap = captureEditSnapshot()
  if (!snap) return
  undoStack.value = [...undoStack.value, snap].slice(-UNDO_LIMIT)
}

function clearEditHistory() {
  undoStack.value = []
  editBaseline = null
}

function undoLastEdit() {
  if (!sceneEditMode.value) {
    ElMessage.warning('请先进入编辑场景')
    return
  }
  if (!undoStack.value.length) {
    ElMessage.info('没有可撤销的操作')
    return
  }
  const prev = undoStack.value[undoStack.value.length - 1]
  undoStack.value = undoStack.value.slice(0, -1)
  applyEditSnapshot(prev)
  refreshDirtyFromBaseline()
  scheduleRebuild(false)
  emitStats()
  ElMessage.success('已撤销上一步')
}

/**
 * 按「单排」强制重编号：左编号从该排左端起，右编号从该排右端起。
 * 删除/替换机柜后调用，消除断号；序号从「连续编号」起始值起。
 */
function renumberRowsAfterEdit(rows: number[]) {
  const sl = sceneLayout.value
  const data = layout.value
  if (!sl || !data) return

  const uniqueRows = [...new Set(rows.filter((r) => r >= 1 && r <= sl.rows))]
  if (!uniqueRows.length) return

  const kindsByRow = Array.from({ length: sl.rows }, (_, ri) => getRow(sl, ri + 1))
  const nextCodes = renumberRackSlots({
    rows: sl.rows,
    cols: sl.cols,
    kindsByRow,
    existing: getSceneSlotCodesMatrix(),
    codePrefix: data.code_prefix || codeBatchPrefix.value || 'A',
    fromRight: labelSide.value === 'right',
    start: Math.max(1, Number(codeBatchStart.value) || 1),
    targetRows: uniqueRows,
  })

  layout.value = { ...data, slot_codes: nextCodes }
}

/** 手动更新全部机柜编号（按当前编号方向与前缀） */
function updateAllRackCodes() {
  if (!sceneEditMode.value) {
    ElMessage.warning('请先点击「编辑场景」')
    return
  }
  const sl = sceneLayout.value
  const data = layout.value
  if (!sl || !data) {
    ElMessage.warning('请先选择机房')
    return
  }
  pushUndoSnapshot()
  const allRows = Array.from({ length: sl.rows }, (_, i) => i + 1)
  renumberRowsAfterEdit(allRows)
  dirty.value = true
  scheduleRebuild(false)
  ElMessage.success(
    labelSide.value === 'right'
      ? '已按右编号更新全部机柜编号（未保存）'
      : '已按左编号更新全部机柜编号（未保存）',
  )
}

function formatApiError(e: unknown, fallback: string): string {
  if (e && typeof e === 'object' && 'response' in e) {
    const data = (e as { response?: { data?: { message?: string; detail?: unknown } } }).response
      ?.data
    if (data?.message) return String(data.message)
    if (typeof data?.detail === 'string') return data.detail
  }
  if (e instanceof Error && e.message) return e.message
  return fallback
}

function slotCodesForSave(scene: SceneLayout): string[][] {
  const kindsByRow = Array.from({ length: scene.rows }, (_, ri) => getRow(scene, ri + 1))
  let codes = normalizeSlotCodesMatrix(
    scene.rows,
    scene.cols,
    layout.value?.slot_codes,
    kindsByRow,
  )
  // 机柜格若缺号，按机房预设补齐，避免 422
  const missing = codes.some((row, ri) =>
    row.some((code, ci) => kindsByRow[ri]?.[ci] === 'rack' && !code),
  )
  if (missing) {
    codes = buildPresetSlotCodes({
      rows: scene.rows,
      cols: scene.cols,
      kindsByRow,
      existing: codes,
      codePrefix: layout.value?.code_prefix || codeBatchPrefix.value || 'A',
      fromRight: labelSide.value === 'right',
    })
  }
  return codes
}

function mutateScene(
  next: SceneLayout,
  opts?: { rebuild?: boolean; resetCam?: boolean; renumberRows?: number[] },
) {
  pushUndoSnapshot()
  sceneLayout.value = next
  editRows.value = next.rows
  editCols.value = next.cols
  dirty.value = true
  if (opts?.renumberRows?.length) {
    renumberRowsAfterEdit(opts.renumberRows)
  }
  if (opts?.rebuild !== false) scheduleRebuild(!!opts?.resetCam)
  emitStats()
}

async function saveSlotCode(row: number, col: number, next: string) {
  if (!selectedRoomId.value) return
  const codes = cloneSlotCodes()
  const r = row - 1
  const c = col - 1
  if (!codes[r]) codes[r] = []
  const dup = codes.some((rowCodes, ri) =>
    rowCodes.some((code, ci) => code === next && !(ri === r && ci === c)),
  )
  if (dup) throw new Error(`标号「${next}」已存在`)
  codes[r][c] = next
  await updateRoom(selectedRoomId.value, { code_mode: 'custom', slot_codes: codes })
  await loadLayout(selectedRoomId.value, false)
}

async function applyContinuousCodes() {
  if (!sceneEditMode.value) {
    ElMessage.warning('请先点击「编辑场景」')
    return
  }
  const prefixExpr =
    (layout.value?.code_prefix || codeBatchPrefix.value || 'A').trim() || 'A'
  const start = Math.max(1, Number(codeBatchStart.value) || 1)
  const fromRight = labelSide.value === 'right'
  const sl = sceneLayout.value
  if (!sl || !layout.value) {
    ElMessage.warning('请先选择机房')
    return
  }
  try {
    expandRowPrefixes(prefixExpr, sl.rows)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '编号前缀无效')
    return
  }
  pushUndoSnapshot()
  const kindsByRow = Array.from({ length: sl.rows }, (_, ri) => getRow(sl, ri + 1))
  const codes = renumberRackSlots({
    rows: sl.rows,
    cols: sl.cols,
    kindsByRow,
    existing: [],
    codePrefix: prefixExpr,
    fromRight,
    start,
  })
  layout.value = {
    ...layout.value,
    code_prefix: prefixExpr,
    slot_codes: codes,
  }
  dirty.value = true
  showCodeBatch.value = false
  scheduleRebuild(false)
  ElMessage.success(
    fromRight
      ? '已按右编号预览（每排从右端起），请保存布局'
      : '已按左编号预览（每排从左端起），请保存布局',
  )
}

async function saveSelectedCode() {
  const rack = selectedRack.value
  if (!rack) return
  const next = editingCode.value.trim()
  if (!next) {
    ElMessage.warning('标号不能为空')
    return
  }
  savingCode.value = true
  try {
    await saveSlotCode(rack.row_no, rack.column_no, next)
    ElMessage.success('标号已更新')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    savingCode.value = false
  }
}

function selectRack(rack: RoomMonitorRack | null) {
  if (!rack) return
  selectedRackId.value = rack.id
  editingCode.value = rack.code
  selectedCell.value = null
  refreshFixedSelection()
  for (const [id, obj] of rackMeshes) {
    obj.traverse((child) => {
      const mesh = child as THREE.Mesh
      if (!mesh.isMesh) return
      const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
      for (const m of mats) {
        const std = m as THREE.MeshStandardMaterial
        if (std.emissive) {
          std.emissiveIntensity = id === rack.id ? 0.35 : std.userData.baseEmissive || 0.05
        }
      }
    })
  }
}

function resolveRackFromHit(hit: {
  cellType?: string
  rackId?: string
  row?: number
  col?: number
} | null): RoomMonitorRack | null {
  if (!hit || !layout.value) return null
  if (hit.rackId) {
    return layout.value.racks.find((r) => r.id === hit.rackId) || null
  }
  if (hit.cellType === 'rack' && hit.row != null && hit.col != null) {
    return (
      layout.value.racks.find((r) => r.row_no === hit.row && r.column_no === hit.col) || null
    )
  }
  return null
}

/** 非编辑态：双击机柜打开内部布局 */
function onCanvasDblClick(event: MouseEvent) {
  if (sceneEditMode.value || rackDialogVisible.value) return
  if (event.button !== 0 && event.button != null) return
  const hit = pickCell(event)
  if (!hit || hit.cellType !== 'rack') return
  event.preventDefault()
  event.stopPropagation()
  const rack = resolveRackFromHit(hit)
  if (!rack) {
    ElMessage.info('该机柜位尚未关联实体机柜，请先保存布局或在机房管理中创建')
    return
  }
  selectRack(rack)
  void openRackDialog(rack)
}

function resolveCellAt(row: number, col: number): {
  cellType: string
  rackId?: string
  row: number
  col: number
} | null {
  const sl = sceneLayout.value
  if (!sl) return null
  const kinds = getRow(sl, row)
  const kind = kinds[col - 1] || 'empty'
  let rackId: string | undefined
  if (kind === 'rack') {
    for (const [id, mesh] of rackMeshes) {
      if (mesh.userData.row === row && mesh.userData.col === col) {
        rackId = id
        break
      }
    }
  }
  return { cellType: kind, rackId, row, col }
}

function pickCell(event: { clientX: number; clientY: number }): {
  cellType?: string
  rackId?: string
  row?: number
  col?: number
} | null {
  if (!hostRef.value || !camera) return null
  const rect = hostRef.value.getBoundingClientRect()
  if (rect.width < 1 || rect.height < 1) return null
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(pointer, camera)
  const targets = cellPickTargets.length ? cellPickTargets : roomGroup ? [roomGroup] : []
  if (targets.length) {
    const hits = raycaster.intersectObjects(targets, true)
    for (const hit of hits) {
      let obj: THREE.Object3D | null = hit.object
      while (obj) {
        if (obj.userData.cellType || obj.userData.rackId) {
          return {
            cellType: obj.userData.cellType as string | undefined,
            rackId: obj.userData.rackId as string | undefined,
            row: obj.userData.row as number | undefined,
            col: obj.userData.col as number | undefined,
          }
        }
        obj = obj.parent
      }
    }
  }
  // 网格地板兜底：提升点击速度与空位命中率
  const floor = clientToFloor(event.clientX, event.clientY)
  if (!floor) return null
  const cell = worldToCell(floor.x, floor.z)
  if (!cell) return null
  return resolveCellAt(cell.row, cell.col)
}

function worldToCell(
  worldX: number,
  worldZ: number,
  opts?: { expand?: boolean },
): { row: number; col: number } | null {
  if (!gridMeta) return null
  const col = Math.round((worldX - gridMeta.startX) / gridMeta.pitchX) + 1
  const row = Math.round((worldZ - gridMeta.startZ) / gridMeta.pitchZ) + 1
  if (opts?.expand) {
    return {
      row: Math.max(1, Math.min(50, row)),
      col: Math.max(1, Math.min(50, col)),
    }
  }
  return {
    row: Math.max(1, Math.min(gridMeta.rows, row)),
    col: Math.max(1, Math.min(gridMeta.cols, col)),
  }
}

function clientToFloor(clientX: number, clientY: number): THREE.Vector3 | null {
  if (!hostRef.value || !camera) return null
  const rect = hostRef.value.getBoundingClientRect()
  if (rect.width < 1 || rect.height < 1) return null
  pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(pointer, camera)
  if (!raycaster.ray.intersectPlane(dragPlane, dragTarget)) return null
  return dragTarget.clone()
}

function applyPresetCodesToScene(scene: SceneLayout) {
  const data = layout.value
  if (!data) return
  const existing = cloneSlotCodes()
  const kindsByRow = Array.from({ length: scene.rows }, (_, ri) => getRow(scene, ri + 1))
  const nextCodes = buildPresetSlotCodes({
    rows: scene.rows,
    cols: scene.cols,
    kindsByRow,
    existing,
    codePrefix: data.code_prefix || codeBatchPrefix.value || 'A',
    fromRight: labelSide.value === 'right',
  })
  layout.value = { ...data, slot_codes: nextCodes }
  if ((data.code_prefix || '').trim()) {
    codeBatchPrefix.value = (data.code_prefix || 'A').trim()
  }
}

function applyGrid() {
  if (!sceneEditMode.value) {
    ElMessage.warning('请先点击「编辑场景」')
    return
  }
  if (!sceneLayout.value) return
  pushUndoSnapshot()
  const prev = sceneLayout.value
  const next = applyGridSize(prev, editRows.value, editCols.value)
  sceneLayout.value = next
  editRows.value = next.rows
  editCols.value = next.cols
  dirty.value = true
  // 扩排/扩列：按机房预设编号补齐新格，保留已有编号
  applyPresetCodesToScene(next)
  scheduleRebuild(true)
  emitStats()
  ElMessage.success(`已应用网格 ${next.rows}×${next.cols}（未保存）`)
}

async function saveSceneLayout() {
  if (!selectedRoomId.value || !sceneLayout.value) return
  if (!sceneEditMode.value && !dirty.value) {
    ElMessage.info('当前为浏览模式，请先编辑场景')
    return
  }
  if (!dirty.value) {
    ElMessage.info('没有需要保存的改动')
    return
  }
  savingLayout.value = true
  try {
    const persist = toPersistLayout(sceneLayout.value)
    const slotCodes = slotCodesForSave(persist)
    layout.value = layout.value ? { ...layout.value, slot_codes: slotCodes } : layout.value
    await updateRoom(selectedRoomId.value, {
      pillar_layout: persist,
      rack_rows: persist.rows,
      rack_columns: persist.cols,
      row_layout: Array.from({ length: persist.rows }, () => persist.cols),
      layout_mode: 'manual',
      code_mode: 'custom',
      code_prefix: layout.value?.code_prefix || codeBatchPrefix.value || 'A',
      slot_codes: slotCodes,
    })
    dirty.value = false
    sceneEditMode.value = false
    clearEditHistory()
    emit('edit-mode-change', false)
    await loadLayout(selectedRoomId.value, false)
    ElMessage.success('场景布局已保存，已退出编辑')
  } catch (e) {
    ElMessage.error(formatApiError(e, '保存布局失败'))
  } finally {
    savingLayout.value = false
  }
}

function restoreFullRacks() {
  if (!sceneEditMode.value) {
    ElMessage.warning('请先点击「编辑场景」')
    return
  }
  if (!sceneLayout.value) return
  pushUndoSnapshot()
  const rows = editRows.value || sceneLayout.value.rows
  const cols = editCols.value || sceneLayout.value.cols
  const next = buildFullRackGrid(rows, cols)
  selectedCell.value = null
  sceneLayout.value = next
  editRows.value = next.rows
  editCols.value = next.cols
  dirty.value = true
  applyPresetCodesToScene(next)
  scheduleRebuild(true)
  emitStats()
  ElMessage.success('已恢复满柜网格（未保存）')
}

function deleteSelectedCell() {
  const sel = selectedCell.value
  if (!sel || sel.kind === 'empty') {
    ElMessage.warning('请先选中要删除的机柜、立柱或列头柜')
    return
  }
  if (!sceneLayout.value) return
  const deletedKind = sel.kind
  const next = clearAt(sceneLayout.value, sel.row, sel.col)
  selectedCell.value = { row: sel.row, col: sel.col, kind: 'empty' }
  selectedRackId.value = null
  // 删除机柜（或影响占号布局）后，本排自动连续重编号
  mutateScene(next, { renumberRows: [sel.row] })
  if (deletedKind === 'rack') {
    ElMessage.success('已删除机柜，本排编号已自动更新（未保存）')
  } else {
    ElMessage.success('已删除（原位留空，本排编号已同步，未保存）')
  }
}

function replaceSelectedCell() {
  const sel = selectedCell.value
  const brush = props.brushKind
  if (!sel) {
    ElMessage.warning('请先单击选中要替换的格子')
    return
  }
  if (!brush) {
    ElMessage.warning('请先在右侧「内置常用模型」中选中替换目标')
    return
  }
  if (!sceneLayout.value) return
  if (sel.kind === brush) {
    ElMessage.info('当前格子已是该模型')
    return
  }
  const next = placeAt(sceneLayout.value, brush, sel.row, sel.col, props.brushMeta)
  selectedCell.value = { row: sel.row, col: sel.col, kind: brush }
  if (brush !== 'rack') selectedRackId.value = null
  mutateScene(next, { renumberRows: [sel.row] })
  ElMessage.success(`已替换为${cellKindLabel(brush)}，本排编号已更新（未保存）`)
}

function selectSceneCell(row: number, col: number, kind: CellKind, rackId?: string) {
  selectedCell.value = { row, col, kind }
  if (kind === 'rack' && rackId) {
    const rack = layout.value?.racks.find((r) => r.id === rackId) || null
    if (rack) {
      selectedRackId.value = rack.id
      editingCode.value = rack.code
    }
  } else if (kind === 'rack') {
    selectedRackId.value = null
  } else {
    selectedRackId.value = null
  }
  refreshCellSelection()
}

function toggleSceneEdit() {
  if (sceneEditMode.value) {
    void exitSceneEdit(false)
    return
  }
  sceneEditMode.value = true
  selectedCell.value = null
  selectedRackId.value = null
  showCodeBatch.value = false
  clearEditHistory()
  editBaseline = captureEditSnapshot()
  dirty.value = false
  refreshCellSelection()
  emit('edit-mode-change', true)
  ElMessage.info('已进入编辑模式：保存布局后退出，或直接退出放弃修改')
}

/** 退出编辑；afterSave=false 时丢弃未保存改动并还原 */
async function exitSceneEdit(afterSave: boolean) {
  const roomId = selectedRoomId.value
  const hadDirty = dirty.value
  sceneEditMode.value = false
  showCodeBatch.value = false
  selectedCell.value = null
  selectedRackId.value = null
  clearEditHistory()
  emit('edit-mode-change', false)
  refreshCellSelection()

  if (afterSave) {
    dirty.value = false
    return
  }

  if (hadDirty && roomId) {
    await loadLayout(roomId, true)
    ElMessage.info('已退出编辑，未保存的修改已丢弃')
    return
  }
  dirty.value = false
  ElMessage.info('已退出编辑')
}

function restoreOrbitControls() {
  if (controls) controls.enabled = true
  if (renderer?.domElement) renderer.domElement.style.cursor = 'grab'
}

function onPointerDownTrack(event: PointerEvent) {
  pointerDownXY = { x: event.clientX, y: event.clientY }
  dragMoved = false
  draggingFixed = false
  dragFrom = null
  dragPreview = null

  if (!sceneEditMode.value || event.button !== 0) return
  const hit = pickCell(event)
  if (
    hit?.cellType &&
    isFixedKind(hit.cellType as CellKind) &&
    hit.row != null &&
    hit.col != null
  ) {
    draggingFixed = true
    dragFrom = { row: hit.row, col: hit.col, kind: hit.cellType as CellKind }
    dragPreview = { row: hit.row, col: hit.col }
    selectFixed(hit.row, hit.col, hit.cellType as CellKind)
    if (controls) controls.enabled = false
    renderer?.domElement.setPointerCapture?.(event.pointerId)
    if (renderer?.domElement) renderer.domElement.style.cursor = 'grabbing'
    event.preventDefault()
  }
}

function applyDragMove(event: PointerEvent) {
  if (!draggingFixed || !dragFrom || !camera || !gridMeta) return
  if (Math.hypot(event.clientX - pointerDownXY.x, event.clientY - pointerDownXY.y) > 4) {
    dragMoved = true
  }
  if (!dragMoved) return

  const floor = clientToFloor(event.clientX, event.clientY)
  if (!floor) return
  const cell = worldToCell(floor.x, floor.z)
  if (!cell) return
  dragPreview = cell
  const mesh = fixedMeshes.get(`${dragFrom.kind}:${dragFrom.row}:${dragFrom.col}`)
  if (mesh) {
    mesh.position.x = gridMeta.startX + (cell.col - 1) * gridMeta.pitchX
    mesh.position.z = gridMeta.startZ + (cell.row - 1) * gridMeta.pitchZ
  }
}

function onPointerMove(event: PointerEvent) {
  if (draggingFixed) {
    pendingDragEvent = event
    if (dragMoveRaf) return
    dragMoveRaf = requestAnimationFrame(() => {
      dragMoveRaf = 0
      if (pendingDragEvent) applyDragMove(pendingDragEvent)
      pendingDragEvent = null
    })
    return
  }
  pendingHoverEvent = event
  if (hoverRaf) return
  hoverRaf = requestAnimationFrame(() => {
    hoverRaf = 0
    if (pendingHoverEvent) updateCellHover(pendingHoverEvent)
    pendingHoverEvent = null
  })
}

function ensureHoverMesh() {
  if (hoverMesh || !roomGroup) return
  hoverMesh = new THREE.Mesh(
    new THREE.BoxGeometry(RACK_W + 0.1, RACK_H + 0.12, RACK_D + 0.12),
    new THREE.MeshBasicMaterial({
      color: 0x3aa0ff,
      transparent: true,
      opacity: 0.22,
      depthWrite: false,
    }),
  )
  hoverMesh.visible = false
  hoverMesh.renderOrder = 2
  roomGroup.add(hoverMesh)
}

function updateCellHover(event: PointerEvent) {
  if (!gridMeta || !roomGroup) return
  const hit = pickCell(event)
  if (!hit || hit.row == null || hit.col == null) {
    if (hoverMesh) hoverMesh.visible = false
    hoverKey = ''
    if (hostRef.value) hostRef.value.style.cursor = ''
    return
  }
  const key = `${hit.row}:${hit.col}:${hit.cellType || ''}`
  const selected =
    !!selectedCell.value &&
    selectedCell.value.row === hit.row &&
    selectedCell.value.col === hit.col
  ensureHoverMesh()
  if (!hoverMesh) return
  if (key !== hoverKey || !hoverMesh.visible) {
    hoverMesh.position.set(
      gridMeta.startX + (hit.col - 1) * gridMeta.pitchX,
      RACK_H / 2,
      gridMeta.startZ + (hit.row - 1) * gridMeta.pitchZ,
    )
  }
  hoverMesh.visible = true
  const mat = hoverMesh.material as THREE.MeshBasicMaterial
  mat.opacity = selected ? 0.32 : 0.2
  mat.color.setHex(selected ? 0xf5a623 : 0x3aa0ff)
  if (hostRef.value) {
    hostRef.value.style.cursor =
      sceneEditMode.value || hit.cellType === 'rack' ? 'pointer' : ''
  }
  hoverKey = key
}

function onLabelSideChange() {
  const sl = sceneLayout.value
  if (!sl || !layout.value) {
    scheduleRebuild(false)
    return
  }
  if (sceneEditMode.value) {
    // v-model 已切到新方向：先按旧方向压栈，再按新方向重编号
    const newSide = labelSide.value
    const oldSide = newSide === 'left' ? 'right' : 'left'
    labelSide.value = oldSide
    pushUndoSnapshot()
    labelSide.value = newSide
  }
  const allRows = Array.from({ length: sl.rows }, (_, i) => i + 1)
  renumberRowsAfterEdit(allRows)
  if (sceneEditMode.value) dirty.value = true
  // 立即重建，确保标签位置 + 号码同步（右编号从右端起）
  if (rebuildRaf) cancelAnimationFrame(rebuildRaf)
  rebuildRaf = 0
  buildSceneContent(layout.value, false)
  requestAnimationFrame(() => {
    applyLabelVisibility()
    refreshCellSelection()
  })
}

function onPointerClick(event: PointerEvent) {
  const movedFar =
    Math.hypot(event.clientX - pointerDownXY.x, event.clientY - pointerDownXY.y) > 5

  if (draggingFixed && dragFrom) {
    restoreOrbitControls()
    try {
      renderer?.domElement.releasePointerCapture?.(event.pointerId)
    } catch {
      /* ignore */
    }

    if (
      dragMoved &&
      dragPreview &&
      (dragPreview.row !== dragFrom.row || dragPreview.col !== dragFrom.col) &&
      sceneLayout.value
    ) {
      const from = dragFrom
      const to = dragPreview
      const next = moveFixed(sceneLayout.value, from.row, from.col, to.row, to.col)
      selectedCell.value = { row: to.row, col: to.col, kind: from.kind }
      mutateScene(next, { renumberRows: [from.row, to.row] })
    } else if (!movedFar && sceneLayout.value && dragFrom) {
      selectSceneCell(dragFrom.row, dragFrom.col, dragFrom.kind)
    }

    draggingFixed = false
    dragFrom = null
    dragPreview = null
    dragMoved = false
    return
  }

  // 普通拖拽旋转结束后恢复光标；若编辑拖拽中途丢失 pointerup，也兜底恢复
  if (!draggingFixed) restoreOrbitControls()

  if (movedFar) return

  const hit = pickCell(event)
  if (!hit || hit.row == null || hit.col == null) return

  if (sceneEditMode.value) {
    if (!sceneLayout.value) return
    // 单击只选中，不自动替换；替换需点右侧「替换」
    const kind = (hit.cellType as CellKind) || 'empty'
    if (
      kind === 'rack' ||
      kind === 'pillar' ||
      kind === 'pillar_round' ||
      kind === 'pdu' ||
      kind === 'power' ||
      kind === 'ac' ||
      kind === 'odf' ||
      kind === 'custom' ||
      kind === 'empty'
    ) {
      selectSceneCell(hit.row, hit.col, kind, hit.rackId)
    }
    return
  }

  if (hit.rackId || hit.cellType === 'rack') {
    const rack = resolveRackFromHit(hit)
    selectRack(rack)
  }
}

function placeLibraryItem(
  kind: CellKind,
  clientX: number,
  clientY: number,
  meta?: CellProp | null,
): boolean {
  if (!sceneLayout.value || !sceneEditMode.value) return false
  if (!isPlaceableKind(kind)) return false
  const floor = clientToFloor(clientX, clientY)
  if (!floor) return false
  const cell = worldToCell(floor.x, floor.z, { expand: true })
  if (!cell) return false
  const prev = sceneLayout.value
  const next = placeAt(prev, kind, cell.row, cell.col, meta)
  if (isFixedKind(kind)) {
    selectedCell.value = { row: cell.row, col: cell.col, kind }
  } else {
    selectedCell.value = null
  }
  mutateScene(next, {
    resetCam: next.rows !== prev.rows || next.cols !== prev.cols,
    renumberRows: [cell.row],
  })
  return true
}

function getHostEl(): HTMLElement | null {
  return hostRef.value
}

async function openRackDialog(rack?: RoomMonitorRack | null) {
  const target = rack || selectedRack.value
  if (!target) {
    ElMessage.warning('请先选中机柜')
    return
  }
  selectedRackId.value = target.id
  editingCode.value = target.code
  rackDialogVisible.value = true
  setLabelsHidden(true)
  rackDialogLoading.value = true
  rackDialogError.value = ''
  rackDialogRack.value = null
  rackDialogSlots.value = []
  rackDialogPower.value = 0
  try {
    const data = await getRackLayout(target.id)
    rackDialogRack.value = data.rack
    rackDialogSlots.value = data.slots
    rackDialogPower.value = data.total_power || 0
  } catch (e) {
    rackDialogError.value = formatApiError(e, '加载机柜布局失败')
  } finally {
    rackDialogLoading.value = false
  }
}

function closeRackDialog() {
  rackDialogVisible.value = false
  setLabelsHidden(false)
  applyLabelVisibility()
}

async function loadRooms() {
  loading.value = true
  errorMsg.value = ''
  try {
    const all = await fetchDashboardRooms()
    rooms.value = all
    const saved = localStorage.getItem(STORAGE_KEY)
    const preferred =
      (props.preferredRoomId && all.find((r) => r.id === props.preferredRoomId)?.id) ||
      (saved && all.find((r) => r.id === saved)?.id) ||
      all.find((r) => r.rack_count > 0)?.id ||
      all[0]?.id ||
      ''
    selectedRoomId.value = preferred
    if (preferred) await loadLayout(preferred)
    else layout.value = null
    emit('ready')
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '加载机房失败'
  } finally {
    loading.value = false
  }
}

async function loadLayout(roomId: string, resetWorking = true) {
  if (!roomId) return
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await fetchDashboardRoomLayout(roomId)
    layout.value = data
    selectedRackId.value = null
    if (resetWorking) {
      selectedCell.value = null
      dirty.value = false
      sceneLayout.value = parseSceneLayout(
        data.pillar_layout as Record<string, unknown> | null | undefined,
        data.rack_rows,
        data.rack_columns,
      )
      editRows.value = sceneLayout.value.rows
      editCols.value = sceneLayout.value.cols
      sceneEditMode.value = false
      emit('edit-mode-change', false)
      if (data.code_prefix) {
        codeBatchPrefix.value = data.code_prefix
      }
    } else if (!sceneLayout.value) {
      sceneLayout.value = parseSceneLayout(
        data.pillar_layout as Record<string, unknown> | null | undefined,
        data.rack_rows,
        data.rack_columns,
      )
      editRows.value = sceneLayout.value.rows
      editCols.value = sceneLayout.value.cols
    }
    buildSceneContent(data, resetWorking)
    emitStats()
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '加载布局失败'
    layout.value = null
  } finally {
    loading.value = false
  }
}

function initThree() {
  const host = hostRef.value
  if (!host) return

  scene = new THREE.Scene()
  scene.background = new THREE.Color(0xd9e6f5)
  // 初始轻雾；具体 near/far 在重建场景时按机房尺寸再校准
  scene.fog = new THREE.Fog(0xd9e6f5, 36, 110)

  const w = host.clientWidth || 800
  const h = host.clientHeight || 560
  camera = new THREE.PerspectiveCamera(40, w / h, 0.1, 260)
  camera.position.set(7, 4.6, 8.5)

  renderer = new THREE.WebGLRenderer({
    antialias: props.quality !== '1',
    alpha: false,
    powerPreference: 'high-performance',
  })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, props.quality === '2' ? 2 : 1.5))
  renderer.setSize(w, h)
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  host.appendChild(renderer.domElement)

  labelRenderer = new CSS2DRenderer()
  labelRenderer.setSize(w, h)
  labelRenderer.domElement.style.position = 'absolute'
  labelRenderer.domElement.style.inset = '0'
  labelRenderer.domElement.style.pointerEvents = 'none'
  labelRenderer.domElement.style.overflow = 'hidden'
  host.appendChild(labelRenderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.enableRotate = true
  controls.enablePan = true
  controls.enableZoom = true
  controls.minDistance = 2.2
  controls.maxDistance = 70
  // 允许接近水平视角，避免几乎不能上下旋转的感觉
  controls.maxPolarAngle = Math.PI * 0.495
  controls.target.set(0, 0.9, 0)
  renderer.domElement.style.display = 'block'
  renderer.domElement.style.width = '100%'
  renderer.domElement.style.height = '100%'
  renderer.domElement.style.touchAction = 'none'
  renderer.domElement.style.cursor = 'grab'

  const hemi = new THREE.HemisphereLight(0xffffff, 0xb0c0d0, 0.85)
  scene.add(hemi)
  const dir = new THREE.DirectionalLight(0xffffff, 0.85)
  dir.position.set(8, 14, 6)
  dir.castShadow = true
  dir.shadow.mapSize.set(1024, 1024)
  scene.add(dir)
  const fill = new THREE.DirectionalLight(0xa8c8ff, 0.25)
  fill.position.set(-6, 8, -4)
  scene.add(fill)

  renderer.domElement.addEventListener('pointerdown', onPointerDownTrack)
  renderer.domElement.addEventListener('pointermove', onPointerMove)
  renderer.domElement.addEventListener('pointerup', onPointerClick)
  renderer.domElement.addEventListener('pointercancel', onPointerClick)
  renderer.domElement.addEventListener('dblclick', onCanvasDblClick)

  const loop = () => {
    animId = requestAnimationFrame(loop)
    controls?.update()
    if (renderer && scene && camera) renderer.render(scene, camera)
    if (labelRenderer && scene && camera) {
      // 隐藏模式跳过渲染并清空残留 DOM，避免残影
      if (labelVisMode.value === 'hide_all' || rackDialogVisible.value) {
        if (labelRenderer.domElement.style.visibility !== 'hidden') {
          labelRenderer.domElement.style.visibility = 'hidden'
        }
        if (labelRenderer.domElement.childElementCount > 0) {
          labelRenderer.domElement.replaceChildren()
        }
      } else {
        if (labelRenderer.domElement.style.visibility === 'hidden') {
          labelRenderer.domElement.style.visibility = 'visible'
          applyLabelVisibility()
        }
        labelRenderer.render(scene, camera)
      }
    }
  }
  loop()

  resizeObs = new ResizeObserver(() => {
    if (!host || !camera || !renderer || !labelRenderer) return
    const nw = host.clientWidth
    const nh = host.clientHeight
    if (nw < 2 || nh < 2) return
    camera.aspect = nw / nh
    camera.updateProjectionMatrix()
    renderer.setSize(nw, nh)
    labelRenderer.setSize(nw, nh)
  })
  resizeObs.observe(host)
}

function destroyThree() {
  cancelAnimationFrame(animId)
  if (dragMoveRaf) cancelAnimationFrame(dragMoveRaf)
  if (rebuildRaf) cancelAnimationFrame(rebuildRaf)
  dragMoveRaf = 0
  rebuildRaf = 0
  pendingDragEvent = null
  resizeObs?.disconnect()
  resizeObs = null
  clearRoom()
  document
    .querySelectorAll(
      '.webgl-rack-label, .webgl-pdu-label, .webgl-fixed-label, .webgl-label-input, .webgl-rack-screen',
    )
    .forEach((n) => n.remove())
  controls?.dispose()
  controls = null
  if (renderer) {
    renderer.domElement.removeEventListener('pointerdown', onPointerDownTrack)
    renderer.domElement.removeEventListener('pointermove', onPointerMove)
    renderer.domElement.removeEventListener('pointerup', onPointerClick)
    renderer.domElement.removeEventListener('pointercancel', onPointerClick)
    renderer.domElement.removeEventListener('dblclick', onCanvasDblClick)
    renderer.dispose()
    renderer.domElement.remove()
    renderer = null
  }
  if (labelRenderer) {
    labelRenderer.domElement.remove()
    labelRenderer = null
  }
  scene = null
  camera = null
  gridMeta = null
}

function resetCamera() {
  if (!camera || !controls) return
  const roomW = gridMeta?.roomW
  const roomD = gridMeta?.roomD
  if (roomW && roomD) {
    const dist = Math.max(roomW, roomD) * 0.68
    camera.position.set(dist * 0.72, dist * 0.4, dist * 0.78)
    camera.far = Math.max(200, Math.max(roomW, roomD) * 8)
    camera.updateProjectionMatrix()
    controls.maxDistance = Math.max(55, Math.max(roomW, roomD) * 2.8)
    controls.target.set(0, 0.9, 0)
    controls.update()
    return
  }
  if (layout.value && sceneLayout.value) buildSceneContent(layout.value, true)
}

watch(selectedRoomId, (id) => {
  if (!id) return
  localStorage.setItem(STORAGE_KEY, id)
  void loadLayout(id)
})

watch(
  () => props.preferredRoomId,
  (id) => {
    if (id && id !== selectedRoomId.value) selectedRoomId.value = id
  },
)

watch(
  () => props.quality,
  () => {
    if (!renderer) return
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, props.quality === '2' ? 2 : 1.5))
  },
)

watch(
  rackDialogVisible,
  (visible) => {
    setLabelsHidden(visible)
  },
  { immediate: true },
)

watch([labelVisMode, labelFocusRow], () => {
  applyLabelVisibility()
})

onMounted(async () => {
  await nextTick()
  initThree()
  await loadRooms()
})

onBeforeUnmount(() => {
  destroyThree()
})

defineExpose({
  reload: loadRooms,
  resetCamera,
  placeLibraryItem,
  getHostEl,
})
</script>

<template>
  <div class="webgl-room">
    <header class="toolbar">
      <div class="toolbar-left">
        <div class="title-wrap">
          <h3>三维仿真视图 · WebGL</h3>
          <p v-if="layout" class="sub">
            {{ layout.location || layout.room_name }} · {{ layout.racks.length }} 柜
            <template v-if="sceneLayout"> · 网格 {{ sceneLayout.rows }}×{{ sceneLayout.cols }}</template>
          </p>
        </div>
        <div class="scene-actions" aria-label="场景布局操作">
          <button
            type="button"
            class="scene-action-btn edit"
            :class="{ active: sceneEditMode }"
            @click="toggleSceneEdit"
          >
            {{ sceneEditMode ? '退出编辑' : '编辑场景' }}
          </button>
          <button
            type="button"
            class="scene-action-btn save"
            :disabled="savingLayout || !dirty"
            @click="saveSceneLayout"
          >
            {{ savingLayout ? '保存中…' : '保存布局' }}
            <i v-if="dirty && !savingLayout" class="save-dot" aria-hidden="true" />
          </button>
        </div>
      </div>

      <div class="controls">
        <label class="room-select">
          <span>机房</span>
          <select v-model="selectedRoomId" :disabled="loading || !rooms.length">
            <option v-if="!rooms.length" value="">暂无机房</option>
            <option v-for="opt in roomOptions" :key="opt.id" :value="opt.id">
              {{ opt.label }}
            </option>
          </select>
        </label>
        <label class="grid-input">
          <span>编号显隐</span>
          <select v-model="labelVisMode" class="batch-select">
            <option value="all">全部显示</option>
            <option value="hide_all">全部隐藏</option>
            <option value="row_only">单排显示</option>
            <option value="row_hide">单排隐藏</option>
          </select>
        </label>
        <label
          v-if="labelVisMode === 'row_only' || labelVisMode === 'row_hide'"
          class="grid-input"
        >
          <span>排号</span>
          <input
            v-model.number="labelFocusRow"
            class="batch-input num"
            type="number"
            min="1"
            :max="sceneLayout?.rows || 50"
          />
        </label>
        <button type="button" class="tool-btn" @click="resetCamera">复位视角</button>
      </div>
    </header>

    <div v-if="sceneEditMode" class="scene-edit-panel">
      <div class="edit-panel-row">
        <div class="grid-size-setting" title="设置机房排×列；扩排时按机房预设编号补齐">
          <span class="grid-size-label">机房网格大小</span>
          <div class="grid-size-fields">
            <label class="grid-size-field">
              <span>排</span>
              <input v-model.number="editRows" class="batch-input num" type="number" min="1" max="50" />
            </label>
            <span class="grid-size-x" aria-hidden="true">×</span>
            <label class="grid-size-field">
              <span>列</span>
              <input v-model.number="editCols" class="batch-input num" type="number" min="1" max="50" />
            </label>
            <button type="button" class="tool-btn grid-apply" :disabled="!sceneLayout" @click="applyGrid">
              应用
            </button>
          </div>
        </div>

        <button type="button" class="tool-btn" :disabled="savingLayout || !sceneLayout" @click="restoreFullRacks">
          恢复满柜
        </button>
        <button
          type="button"
          class="tool-btn"
          :disabled="!canUndo"
          title="撤销上一步场景编辑"
          @click="undoLastEdit"
        >
          撤销上一步
        </button>
        <button type="button" class="tool-btn" @click="showCodeBatch = !showCodeBatch">连续编号</button>
        <button
          type="button"
          class="tool-btn"
          :disabled="!sceneLayout"
          title="按当前编号方向与起始值，重新连续编排全部机柜编号"
          @click="updateAllRackCodes"
        >
          更新机柜编号
        </button>

        <label class="grid-input">
          <span>编号方向</span>
          <select
            v-model="labelSide"
            class="batch-select"
            title="左编号：该排从左端起编；右编号：从右端起编"
            @change="onLabelSideChange"
          >
            <option value="left">左编号</option>
            <option value="right">右编号</option>
          </select>
        </label>

        <div class="edit-cell-actions">
          <button
            type="button"
            class="dock-btn replace"
            :disabled="!selectedCell || !brushKind"
            @click="replaceSelectedCell"
          >
            替换
          </button>
          <button
            type="button"
            class="dock-btn delete"
            :disabled="!selectedCell || selectedCell.kind === 'empty'"
            @click="deleteSelectedCell"
          >
            删除
          </button>
        </div>
      </div>

      <div v-if="showCodeBatch" class="code-batch in-edit">
        <span>前缀</span>
        <input v-model="codeBatchPrefix" class="batch-input" maxlength="8" />
        <span>起始</span>
        <input v-model.number="codeBatchStart" class="batch-input num" type="number" min="1" />
        <span class="scene-hint">
          按机房预设前缀 · 每排从「{{ labelSide === 'right' ? '右端' : '左端' }}」起 · 需保存布局
        </span>
        <button type="button" class="tool-btn" :disabled="codeBatchSaving" @click="applyContinuousCodes">
          {{ codeBatchSaving ? '应用中…' : '应用到全部机柜位' }}
        </button>
        <button type="button" class="tool-btn" @click="showCodeBatch = false">取消</button>
      </div>

      <p class="scene-hint">
        单击格子选中 · 替换 / 删除后本排自动重编号 · 「撤销上一步」可回退 · 「保存布局」保存并退出 · 「退出编辑」放弃修改
        <template v-if="brushKind">
          · 待替换：{{
            brushKind === 'custom'
              ? brushMeta?.label || '自定义'
              : cellKindLabel(brushKind)
          }}
        </template>
        <template v-if="selectedCell">
          · 已选 第{{ selectedCell.row }}排 / 第{{ selectedCell.col }}列（{{
            selectedCell.kind === 'custom'
              ? selectedCellLabel
              : cellKindLabel(selectedCell.kind)
          }}）
        </template>
        <template v-if="dirty"> · 未保存</template>
      </p>
    </div>

    <div ref="hostRef" class="canvas-host" :class="{ loading }">
      <p v-if="errorMsg" class="hint error">{{ errorMsg }}</p>
      <p v-else-if="!selectedRoomId" class="hint">请选择机房</p>
      <p v-else-if="!layout?.racks.length && !loading && !sceneLayout" class="hint overlay">
        该机房尚未配置机柜，可先在机房管理中布局
      </p>
    </div>

    <aside v-if="selectedRack && !sceneEditMode" class="tip-card">
      <strong>{{ selectedRack.code }}</strong>
      <span>{{ selectedRack.name }}</span>
      <span v-if="selectedSlotPos">
        位置 第{{ selectedSlotPos.row }}排 / 第{{ selectedSlotPos.col }}列
      </span>
      <span>利用率 {{ selectedRack.utilization }}%</span>
      <span>
        {{ selectedRack.occupied_u }}/{{ selectedRack.total_u }}U · {{ selectedRack.device_count }} 台
      </span>
      <div class="tip-edit">
        <label>机柜标号</label>
        <div class="tip-edit-row">
          <input v-model="editingCode" maxlength="50" @keydown.enter.prevent="saveSelectedCode" />
          <button type="button" :disabled="savingCode" @click="saveSelectedCode">保存</button>
        </div>
      </div>
      <button type="button" class="primary" @click="openRackDialog()">查看内部布局</button>
    </aside>

    <p class="gesture-hint">
      <template v-if="sceneEditMode">
        场景编辑 · 可撤销上一步 · 保存布局后退出 · 退出编辑将丢弃未保存修改
      </template>
      <template v-else>
        拖拽旋转 · 滚轮缩放 · 右键平移 · 单击机柜选中 · 双击机柜查看内部布局
      </template>
    </p>

    <Teleport to="body">
      <div v-if="rackDialogVisible" class="rack-dialog-mask" @click.self="closeRackDialog">
        <div class="rack-dialog" role="dialog" aria-modal="true">
          <header>
            <div class="rack-dialog-title">
              <h4>{{ rackDialogRack?.code || selectedRack?.code || '机柜布局' }}</h4>
              <p v-if="rackDialogRack || selectedRack">
                {{ rackDialogRack?.name || selectedRack?.name }}
                <template v-if="selectedSlotPos">
                  · 第{{ selectedSlotPos.row }}排 / 第{{ selectedSlotPos.col }}列
                </template>
              </p>
            </div>
            <button type="button" @click="closeRackDialog">关闭</button>
          </header>
          <div v-if="rackDialogLoading" class="body loading">加载机柜布局…</div>
          <div v-else-if="rackDialogError" class="body error">{{ rackDialogError }}</div>
          <div v-else-if="rackDialogRack" class="body">
            <div class="meta">
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
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.webgl-room {
  position: relative;
  height: 100%;
  min-height: 560px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: #2a3d52;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.toolbar-left {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
  min-width: 0;
}

.title-wrap h3 {
  margin: 0;
  font-size: 14px;
  color: #2a4a6a;
}

.sub {
  margin: 4px 0 0;
  font-size: 11px;
  color: #6b7c8f;
}

/* 场景编辑主操作：居左、强调样式，区别于右侧常规工具 */
.scene-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px;
  border-radius: 10px;
  background: linear-gradient(135deg, #1a4a7a 0%, #0f2f52 100%);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.12) inset,
    0 4px 14px rgba(20, 60, 110, 0.28);
}

.scene-action-btn {
  position: relative;
  height: 32px;
  min-width: 96px;
  padding: 0 14px;
  border: none;
  border-radius: 7px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.scene-action-btn.edit {
  background: #fff;
  color: #163a62;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
}

.scene-action-btn.edit:hover {
  background: #f0f7ff;
  color: #0d4d9c;
}

.scene-action-btn.edit.active {
  background: #3aa0ff;
  color: #fff;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.35);
}

.scene-action-btn.save {
  background: transparent;
  color: #d7e9ff;
  border: 1px solid rgba(215, 233, 255, 0.45);
}

.scene-action-btn.save:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  border-color: rgba(255, 255, 255, 0.7);
}

.scene-action-btn.save:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.scene-action-btn .save-dot {
  position: absolute;
  top: 6px;
  right: 8px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #f5a623;
  box-shadow: 0 0 0 2px rgba(245, 166, 35, 0.25);
}

.controls {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
  flex: 1;
  min-width: 0;
}

.room-select,
.grid-input {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.grid-size-setting {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 3px 8px 3px 10px;
  border-radius: 8px;
  border: 1px solid #c5d5e8;
  background: #f5f9fd;
}

.grid-size-setting.disabled {
  opacity: 0.55;
  background: #eef1f5;
}

.grid-size-label {
  font-size: 12px;
  font-weight: 600;
  color: #3a5570;
  white-space: nowrap;
}

.grid-size-fields {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.grid-size-field {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #6b7c8f;
}

.grid-size-field .batch-input.num {
  width: 52px;
}

.grid-size-x {
  color: #8aa0b5;
  font-size: 13px;
  font-weight: 600;
  padding: 0 2px;
}

.grid-apply {
  margin-left: 2px;
}

.room-select select,
.batch-input,
.tool-btn,
.tip-edit-row input,
.tip-card button {
  height: 28px;
  border-radius: 6px;
  border: 1px solid #b8cce0;
  background: #fff;
  color: #2a3d52;
  padding: 0 10px;
  font-size: 12px;
}

.tool-btn {
  cursor: pointer;
}

.tool-btn:hover {
  border-color: #3aa0ff;
  color: #1a6fd0;
}

.tool-btn.active {
  border-color: #3aa0ff;
  background: #e8f3ff;
  color: #1a6fd0;
}

.tool-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.code-batch,
.scene-edit-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid #c5d5e8;
  border-radius: 10px;
  background: linear-gradient(180deg, #f7fbff, #eef5fc);
}

.edit-panel-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.edit-cell-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.edit-cell-actions .dock-btn {
  min-width: 72px;
  height: 32px;
  padding: 0 14px;
  border-radius: 7px;
  border: none;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.edit-cell-actions .dock-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.edit-cell-actions .dock-btn.replace {
  background: #3aa0ff;
  color: #fff;
}

.edit-cell-actions .dock-btn.replace:hover:not(:disabled) {
  background: #2b8ae6;
}

.edit-cell-actions .dock-btn.delete {
  background: #fff;
  color: #c0352b;
  border: 1px solid #e8a39d;
}

.edit-cell-actions .dock-btn.delete:hover:not(:disabled) {
  background: #fff5f4;
  border-color: #c0352b;
}

.code-batch.in-edit {
  margin: 0;
  background: #fff;
}

.scene-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  border: 1px solid #d7e3ef;
  border-radius: 8px;
  background: #fff;
  font-size: 12px;
}

.scene-hint {
  color: #6b7c8f;
  font-size: 11px;
}

.batch-input {
  width: 72px;
}

.batch-input.num {
  width: 64px;
}

.batch-select {
  height: 28px;
  border-radius: 6px;
  border: 1px solid #b8cce0;
  background: #fff;
  color: #2a3d52;
  padding: 0 6px;
  font-size: 12px;
  min-width: 88px;
}

.canvas-host {
  position: relative;
  flex: 1;
  min-height: 480px;
  border-radius: 10px;
  border: 1px solid #c5d5e5;
  overflow: hidden;
  background: linear-gradient(180deg, #eef5fc, #d5e4f3);
}

.canvas-host > canvas {
  display: block;
  width: 100% !important;
  height: 100% !important;
  touch-action: none;
  cursor: grab;
}

.canvas-host > canvas:active {
  cursor: grabbing;
}

.canvas-host.loading {
  opacity: 0.75;
}

.hint {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  margin: 0;
  color: #6b7c8f;
  z-index: 2;
  pointer-events: none;
}

.hint.error {
  color: #e35d5b;
}

.hint.overlay {
  background: rgba(255, 255, 255, 0.35);
}

.tip-card {
  position: absolute;
  right: 18px;
  top: 72px;
  z-index: 5;
  width: 220px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(160, 190, 220, 0.7);
  box-shadow: 0 8px 24px rgba(40, 70, 110, 0.12);
  font-size: 12px;
}

.tip-card strong {
  font-size: 15px;
  color: #1f2d3d;
}

.tip-edit {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tip-edit-row {
  display: flex;
  gap: 6px;
}

.tip-edit-row input {
  flex: 1;
  min-width: 0;
}

.tip-card .primary {
  margin-top: 8px;
  background: #3aa0ff;
  border-color: #3aa0ff;
  color: #fff;
  cursor: pointer;
}

.gesture-hint {
  margin: 0;
  font-size: 11px;
  color: #6b7c8f;
}
</style>

<style>
.webgl-rack-label {
  padding: 2px 6px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.94);
  color: #e8960f;
  font-size: 11px;
  line-height: 1.3;
  font-weight: 700;
  letter-spacing: 0.02em;
  font-family: 'IBM Plex Mono', ui-monospace, Consolas, monospace;
  box-shadow:
    0 0 0 1px rgba(245, 166, 35, 0.5),
    0 1px 4px rgba(40, 70, 110, 0.1);
  /* 必须 none：标签叠在 canvas 上方，auto 会抢走拖拽导致无法旋转；
     双击查看机柜已由 canvas onCanvasDblClick 处理 */
  pointer-events: none;
  white-space: nowrap;
  transform: translateZ(0);
  text-shadow: none;
}

.webgl-rack-label.muted {
  color: #7a8b9c;
  box-shadow: 0 0 0 1px rgba(160, 180, 200, 0.55);
  text-shadow: none;
}

.webgl-rack-label.is-hidden,
.webgl-pdu-label.is-hidden,
.webgl-fixed-label.is-hidden {
  visibility: hidden !important;
  display: none !important;
}

.webgl-pdu-label,
.webgl-fixed-label {
  padding: 2px 6px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.94);
  color: #ea580c;
  font-size: 11px;
  line-height: 1.3;
  font-weight: 700;
  letter-spacing: 0.02em;
  pointer-events: none;
  white-space: nowrap;
}

.webgl-fixed-label[data-kind='power'] {
  color: #b45309;
}

.webgl-fixed-label[data-kind='ac'] {
  color: #0369a1;
}

.webgl-fixed-label[data-kind='odf'] {
  color: #b45309;
}

.webgl-fixed-label[data-kind='custom'] {
  color: #475569;
}

.webgl-pdu-label {
  font-family: 'IBM Plex Mono', ui-monospace, Consolas, monospace;
  box-shadow: 0 0 0 1px rgba(234, 88, 12, 0.45);
}

.webgl-fixed-label {
  font-family: 'IBM Plex Mono', ui-monospace, Consolas, monospace;
  box-shadow: 0 0 0 1px rgba(100, 120, 140, 0.4);
}

.webgl-label-input {
  width: 64px;
  height: 22px;
  border: 1px solid #f0c000;
  border-radius: 3px;
  text-align: center;
  font-weight: 700;
  font-size: 11px;
  outline: none;
}

.rack-dialog-mask {
  position: fixed;
  inset: 0;
  z-index: 4000;
  background: rgba(20, 30, 45, 0.45);
  display: grid;
  place-items: center;
}

.rack-dialog {
  width: min(560px, 94vw);
  max-height: 86vh;
  overflow: auto;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #d7e3ef;
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.2);
}

.rack-dialog header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid #ebeef5;
}

.rack-dialog-title {
  min-width: 0;
}

.rack-dialog header h4 {
  margin: 0;
  font-size: 16px;
  color: #1f3348;
}

.rack-dialog-title p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #6b7c8f;
}

.rack-dialog header button {
  height: 28px;
  border-radius: 6px;
  border: 1px solid #b8cce0;
  background: #fff;
  color: #2a3d52;
  padding: 0 10px;
  font-size: 12px;
  cursor: pointer;
  flex-shrink: 0;
}

.rack-dialog .body {
  padding: 12px 14px 16px;
}

.rack-dialog .body.loading,
.rack-dialog .body.error {
  min-height: 180px;
  display: grid;
  place-items: center;
}

.rack-dialog .meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin-bottom: 12px;
  font-size: 12px;
  color: #6b7c8f;
}

.rack-dialog-cabinet {
  display: flex;
  justify-content: center;
  max-height: min(68vh, 720px);
  overflow: auto;
  padding: 4px 0;
}
</style>
