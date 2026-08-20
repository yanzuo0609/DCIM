/**
 * 独立设备组：组定义与画布设备解耦，由「类型/模型 + 数量」槽位组成；
 * 拖入拓扑或执行布线时再实例化到画布，并打上组标签供源/目标匹配。
 */

import type { NetworkNode } from '@/api/network'
import type { NetworkDesignModel } from '@/api/networkModelDesign'
import { stampDesignModelOntoCanvas } from '@/utils/designModelToNode'
import { addNodeToGroup, listGroupMembers, nodeInGroup, nodeParentGroups, setNodeGroups } from '@/utils/deviceGroups'
import { groupKindFromRole, layoutGroupGrid, type DeviceGroupKind } from '@/utils/deviceGroupVisual'
import { deviceNamePrefix, nextDeviceName } from '@/utils/topologyClone'
import type { FabricRole } from '@/utils/wiringTypes'
import { FABRIC_ROLE_OPTIONS } from '@/utils/wiringTypes'

/** 组内一种设备规格（可多条，支持同类或异类混合） */
export interface DeviceGroupSlot {
  id: string
  /** 实例名前缀 / 展示名 */
  label: string
  /** 设备实例命名规则，支持 {group}、{label}、{index}、{index:03} */
  name_pattern?: string | null
  role: FabricRole | null
  design_model_id: string | null
  count: number
}

export interface DeviceGroupPortRef {
  node_id: string
  port_id: string
  port_label: string
}

/** 独立于拓扑的设备组内部实例；拖入拓扑时据此创建画布节点。 */
export interface DeviceGroupInstanceDef {
  id: string
  name: string
  role: FabricRole | null
  design_model_id: string | null
  slot_id: string | null
}

export interface DeviceGroupDef {
  /** 稳定组 ID，用于报表、规则引用和跨拓扑追踪；旧数据按组名生成。 */
  id?: string | null
  name: string
  description: string
  /** 显式设备组类型；避免仅靠首台设备角色推断。 */
  group_type?: DeviceGroupKind | null
  /** 组图标用：混合组取首个槽位角色，或用户指定 */
  role: FabricRole | null
  slots: DeviceGroupSlot[]
  /** 项目级组内实例清单，不属于任何单一拓扑。 */
  instances?: DeviceGroupInstanceDef[] | null
  /** 绑定的布线规则 ID：拖入/部署到画布后自动执行 */
  wiring_rule_ids?: string[] | null
  /** 预留规则执行范围：group=仅组内，topology=允许在整个拓扑匹配。 */
  wiring_scope?: 'group' | 'topology'
  /** 拖入拓扑时是否按子组目标数量自动补齐实例；默认开启 */
  auto_generate?: boolean
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
    name_pattern: partial?.name_pattern?.trim() || null,
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
          name_pattern: s.name_pattern?.trim() || null,
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

export function formatDeviceGroupSequenceName(
  pattern: string,
  vars: { group: string; label: string; index: number; prefix?: string; source?: string },
): string {
  const raw = pattern.trim()
  if (!raw) return ''
  return raw
    .replace(/\{index(?::(\d+))?\}/g, (_all, width: string | undefined) =>
      String(vars.index).padStart(Math.max(1, Number(width) || 1), '0'),
    )
    .replaceAll('{group}', vars.group)
    .replaceAll('{label}', vars.label)
    .replaceAll('{prefix}', vars.prefix || '')
    .replaceAll('{source}', vars.source || '')
    .trim()
}

export function syncGroupInstances(
  groupName: string,
  slots: DeviceGroupSlot[],
  existing: DeviceGroupInstanceDef[] | null | undefined,
): DeviceGroupInstanceDef[] {
  const available = (existing || []).filter((item) => item?.id && item?.name)
  if (!slots.length) return available.map((item) => ({ ...item }))
  const used = new Set<string>()
  const result: DeviceGroupInstanceDef[] = []
  for (const slot of slots) {
    const candidates = available.filter(
      (item) =>
        !used.has(item.id) &&
        (item.slot_id === slot.id ||
          (!item.slot_id && item.design_model_id === slot.design_model_id && item.role === slot.role)),
    )
    const count = Math.max(0, Math.floor(Number(slot.count) || 0))
    for (let index = 0; index < count; index += 1) {
      const reused = candidates[index]
      if (reused) {
        used.add(reused.id)
        result.push({ ...reused, slot_id: slot.id })
        continue
      }
      const base = (slot.label || roleLabel(slot.role) || '设备').trim()
      const generatedName = formatDeviceGroupSequenceName(slot.name_pattern || '', {
        group: groupName,
        label: base,
        index: index + 1,
      })
      result.push({
        id: `DGI-${crypto.randomUUID().replace(/-/g, '').slice(0, 12).toUpperCase()}`,
        name: generatedName || `${groupName}-${base}-${String(index + 1).padStart(2, '0')}`,
        role: slot.role || null,
        design_model_id: slot.design_model_id || null,
        slot_id: slot.id,
      })
    }
  }
  return result
}

export function normalizeDeviceGroupId(id: unknown, name: string): string {
  const existing = typeof id === 'string' ? id.trim() : ''
  if (existing) return existing
  let hash = 2166136261
  for (const char of name.trim().toLowerCase()) {
    hash ^= char.charCodeAt(0)
    hash = Math.imul(hash, 16777619)
  }
  return `DG-${(hash >>> 0).toString(16).toUpperCase().padStart(8, '0')}`
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
        kind === 'server'
          ? '服务器'
          : kind === 'security'
            ? '安全'
            : kind === 'core'
              ? '核心'
              : kind === 'aggregation'
                ? '汇聚'
                : kind === 'access'
                  ? '接入'
                  : '混合'
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
  const subRef = subgroupRef(g, slot.id)
  return listGroupMembers(nodes, g).filter((n) => {
    if (nodeInGroup(n, subRef) || n.contract_device_name === slotMark) return true
    // 新建组中手选的已有设备优先按设计模型或角色占用子组名额，避免拖入时重复生成。
    if (slot.design_model_id) return n.design_model_id === slot.design_model_id
    if (slot.role) return n.network_role === slot.role
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
  const claimedNodeIds = new Set<string>()

  for (const slot of slots) {
    const subRef = subgroupRef(groupName, slot.id)
    const existing = listSlotInstances(working, groupName, slot)
      .filter((node) => !claimedNodeIds.has(node.id))
      .slice(0, Math.max(0, Math.floor(slot.count)))
    for (const node of existing) claimedNodeIds.add(node.id)
    const need = Math.max(0, Math.floor(slot.count) - existing.length)
    for (const n of existing) {
      if (!addNodeToGroup(n, groupName)) {
        const other = nodeParentGroups(n).find((p) => p !== groupName)
        warnings.push(
          `设备「${n.name}」已属于组「${other || '其他组'}」，不可再加入「${groupName}」`,
        )
        continue
      }
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
      const patterned = formatDeviceGroupSequenceName(slot.name_pattern || '', {
        group: groupName,
        label: base,
        index: existing.length + i + 1,
      })
      node.name = nextDeviceName(working, { ...node, name: patterned || base })
      node.contract_device_name = `dgslot:${slot.id}`
      if (slot.role) node.network_role = slot.role
      setNodeGroups(node, [groupName, subRef])
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
  return nodes.filter((n) => n.on_canvas !== false && nodeInGroup(n, groupName)).length
}
