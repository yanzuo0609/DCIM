/**
 * 独立设备组：组定义与画布设备解耦，由「类型/模型 + 数量」槽位组成；
 * 拖入拓扑或执行布线时再实例化到画布，并打上组标签供源/目标匹配。
 */

import type { NetworkNode } from '@/api/network'
import type { NetworkDesignModel } from '@/api/networkModelDesign'
import { stampDesignModelOntoCanvas } from '@/utils/designModelToNode'
import { addNodeToGroup, listGroupMembers, nodeInGroup } from '@/utils/deviceGroups'
import { groupKindFromRole, layoutGroupGrid } from '@/utils/deviceGroupVisual'
import { deviceNamePrefix, nextDeviceName } from '@/utils/topologyClone'
import type { FabricRole } from '@/utils/wiringTypes'
import { FABRIC_ROLE_OPTIONS } from '@/utils/wiringTypes'

/** 组内一种设备规格（可多条，支持同类或异类混合） */
export interface DeviceGroupSlot {
  id: string
  /** 实例名前缀 / 展示名 */
  label: string
  role: FabricRole | null
  design_model_id: string | null
  count: number
}

export interface DeviceGroupPortRef {
  node_id: string
  port_id: string
  port_label: string
}

export interface DeviceGroupDef {
  name: string
  description: string
  /** 组图标用：混合组取首个槽位角色，或用户指定 */
  role: FabricRole | null
  slots: DeviceGroupSlot[]
  /** 绑定的布线规则 ID：拖入/部署到画布后自动执行 */
  wiring_rule_ids?: string[] | null
  /** @deprecated 兼容旧单规格组 */
  planned_count?: number | null
  /** @deprecated */
  design_model_id?: string | null
  port_pool?: DeviceGroupPortRef[] | null
}

/** 子组引用分隔符：父组名::子组id */
export const SUBGROUP_REF_SEP = '::'

/** 生成可写入 device_groups / 布线规则的子组引用 */
export function subgroupRef(groupName: string, slotId: string): string {
  return `${groupName.trim()}${SUBGROUP_REF_SEP}${slotId}`
}

export function parseSubgroupRef(
  ref: string,
): { groupName: string; slotId: string } | null {
  const raw = (ref || '').trim()
  const i = raw.indexOf(SUBGROUP_REF_SEP)
  if (i <= 0) return null
  const groupName = raw.slice(0, i).trim()
  const slotId = raw.slice(i + SUBGROUP_REF_SEP.length).trim()
  if (!groupName || !slotId) return null
  return { groupName, slotId }
}

/** 从规则里的组/子组引用提取需要物化的父组名 */
export function parentGroupNamesFromRefs(refs: string[]): string[] {
  const names = new Set<string>()
  for (const r of refs) {
    const t = (r || '').trim()
    if (!t) continue
    const sub = parseSubgroupRef(t)
    names.add(sub ? sub.groupName : t)
  }
  return [...names]
}

export function subgroupDisplayLabel(
  groupName: string,
  slot: Pick<DeviceGroupSlot, 'id' | 'label' | 'role'>,
): string {
  const sub = (slot.label || '').trim() || roleLabel(slot.role) || '子组'
  return `${groupName} / ${sub}`
}

/** 布线下拉：整组 + 各子组 */
export function buildWiringGroupSelectOptions(
  catalog: Array<{
    name: string
    slots?: DeviceGroupSlot[] | null
    role?: FabricRole | null
    planned_count?: number | null
    design_model_id?: string | null
  }>,
): Array<{ value: string; label: string; kind: 'group' | 'subgroup' }> {
  const out: Array<{ value: string; label: string; kind: 'group' | 'subgroup' }> = []
  const sorted = [...catalog]
    .filter((g) => g?.name)
    .sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
  for (const g of sorted) {
    const slots = migrateSlotsFromLegacy(g)
    out.push({
      value: g.name,
      label: slots.length > 1 ? `${g.name}（整组）` : g.name,
      kind: 'group',
    })
    for (const slot of slots) {
      out.push({
        value: subgroupRef(g.name, slot.id),
        label: subgroupDisplayLabel(g.name, slot),
        kind: 'subgroup',
      })
    }
  }
  return out
}

export function newSlotId(): string {
  return crypto.randomUUID()
}

export function emptySlot(partial?: Partial<DeviceGroupSlot>): DeviceGroupSlot {
  return {
    id: partial?.id || newSlotId(),
    label: partial?.label || '',
    role: partial?.role ?? null,
    design_model_id: partial?.design_model_id ?? null,
    count: partial?.count != null && partial.count > 0 ? Math.floor(partial.count) : 1,
  }
}

/** 旧字段 → slots */
export function migrateSlotsFromLegacy(raw: {
  slots?: DeviceGroupSlot[] | null
  planned_count?: number | null
  design_model_id?: string | null
  role?: FabricRole | null
  name?: string
}): DeviceGroupSlot[] {
  if (Array.isArray(raw.slots) && raw.slots.length) {
    return raw.slots
      .filter((s) => s && (s.count > 0 || s.design_model_id || s.label))
      .map((s) =>
        emptySlot({
          id: s.id || newSlotId(),
          label: (s.label || '').trim() || roleLabel(s.role) || '设备',
          role: s.role ?? raw.role ?? null,
          design_model_id: s.design_model_id || null,
          count: Math.max(1, Math.floor(Number(s.count) || 1)),
        }),
      )
  }
  const planned =
    raw.planned_count != null && Number.isFinite(Number(raw.planned_count))
      ? Math.max(0, Math.floor(Number(raw.planned_count)))
      : 0
  if (planned > 0 || raw.design_model_id) {
    return [
      emptySlot({
        label: roleLabel(raw.role) || raw.name || '设备',
        role: raw.role ?? null,
        design_model_id: raw.design_model_id || null,
        count: Math.max(1, planned || 1),
      }),
    ]
  }
  return []
}

function roleLabel(role: FabricRole | null | undefined): string {
  if (!role) return ''
  return FABRIC_ROLE_OPTIONS.find((o) => o.value === role)?.label || role
}

export function totalSlotCount(slots: DeviceGroupSlot[] | null | undefined): number {
  if (!slots?.length) return 0
  return slots.reduce((sum, s) => sum + Math.max(0, Math.floor(Number(s.count) || 0)), 0)
}

export function summarizeSlots(
  slots: DeviceGroupSlot[] | null | undefined,
  models?: Array<{ id: string; name: string }>,
): string {
  if (!slots?.length) return '未配置设备'
  return slots
    .map((s) => {
      const modelName = s.design_model_id
        ? models?.find((m) => m.id === s.design_model_id)?.name
        : null
      const kind = groupKindFromRole(s.role)
      const kindText =
        kind === 'server' ? '服务器' : kind === 'security' ? '安全' : '交换机'
      const title = modelName || s.label || roleLabel(s.role) || kindText
      return `${title}×${Math.max(0, s.count)}`
    })
    .join(' + ')
}

/** 当前拓扑上已占用该槽位的实例 */
export function listSlotInstances(
  nodes: NetworkNode[],
  groupName: string,
  slot: DeviceGroupSlot,
): NetworkNode[] {
  const g = groupName.trim()
  const label = (slot.label || '').trim()
  const slotMark = `dgslot:${slot.id}`
  return listGroupMembers(nodes, g).filter((n) => {
    if (n.contract_device_name === slotMark) return true
    if (slot.design_model_id && n.design_model_id === slot.design_model_id) {
      if (!label) return true
      return deviceNamePrefix(n.name, n.kind) === label
    }
    if (label) return deviceNamePrefix(n.name, n.kind) === label
    return false
  })
}

export interface MaterializeGroupResult {
  created: NetworkNode[]
  reused: NetworkNode[]
  placed: NetworkNode[]
  warnings: string[]
}

/**
 * 按组槽位在拓扑上补齐实例（同拓扑不超量），打上组标签。
 * onCanvas=true 时放到画布；false 时仅作为组库存（布线匹配需再打开画布可见性时可改）。
 */
export function materializeGroupSlots(opts: {
  groupName: string
  def: DeviceGroupDef
  topologyId: string
  nodes: NetworkNode[]
  models: NetworkDesignModel[]
  originX?: number
  originY?: number
  onCanvas?: boolean
}): MaterializeGroupResult {
  const {
    groupName,
    def,
    topologyId,
    models,
    originX = 80,
    originY = 80,
    onCanvas = true,
  } = opts
  const working = [...opts.nodes]
  const created: NetworkNode[] = []
  const reused: NetworkNode[] = []
  const warnings: string[] = []
  const slots = migrateSlotsFromLegacy(def)

  for (const slot of slots) {
    const subRef = subgroupRef(groupName, slot.id)
    const existing = listSlotInstances(working, groupName, slot)
    const need = Math.max(0, Math.floor(slot.count) - existing.length)
    for (const n of existing) {
      addNodeToGroup(n, groupName)
      addNodeToGroup(n, subRef)
      if (slot.role && !n.network_role) n.network_role = slot.role
      reused.push(n)
    }
    if (need <= 0) continue

    const model = slot.design_model_id
      ? models.find((m) => m.id === slot.design_model_id)
      : null
    if (!model) {
      warnings.push(
        `子组「${slot.label || roleLabel(slot.role) || '未命名'}」缺少设计模型，无法创建 ${need} 台`,
      )
      continue
    }

    for (let i = 0; i < need; i++) {
      const node = stampDesignModelOntoCanvas(model, topologyId, 0, 0, working)
      const base = (slot.label || model.name || '设备').trim()
      node.name = nextDeviceName(working, { ...node, name: base })
      node.contract_device_name = `dgslot:${slot.id}`
      if (slot.role) node.network_role = slot.role
      addNodeToGroup(node, groupName)
      addNodeToGroup(node, subRef)
      node.on_canvas = onCanvas
      working.push(node)
      created.push(node)
    }
  }

  const toLayout = onCanvas
    ? [...created, ...reused.filter((n) => n.on_canvas === false)]
    : created
  for (const n of toLayout) n.on_canvas = onCanvas
  if (onCanvas && toLayout.length) {
    const positions = layoutGroupGrid(toLayout.length, originX, originY)
    for (let i = 0; i < toLayout.length; i++) {
      toLayout[i].pos_x = positions[i].x
      toLayout[i].pos_y = positions[i].y
      toLayout[i].on_canvas = true
    }
  }

  return {
    created,
    reused,
    placed: toLayout,
    warnings,
  }
}

/** 组在当前拓扑已实例数量（有组标签的节点） */
export function countGroupOnTopology(nodes: NetworkNode[], groupName: string): number {
  return nodes.filter((n) => nodeInGroup(n, groupName)).length
}
