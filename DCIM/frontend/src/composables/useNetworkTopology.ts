import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  type CanvasLinkInput,
  type CanvasNodeInput,
  type NetworkLink,
  type NetworkNode,
  type NetworkTopology,
  createNetworkTopology,
  defaultSlots,
  deleteNetworkTopology,
  getNetworkTopologyDetail,
  listNetworkTopologies,
  saveNetworkCanvas,
} from '@/api/network'

function clampPortLayoutForApi(layout: NetworkNode['port_layout']) {
  if (!layout) return null
  const rack = layout.rack_width_mm ?? 600
  return {
    ...layout,
    layout_locked: layout.layout_locked === true,
    rack_width_mm: Math.max(200, Math.min(1200, rack)),
    uplink_port_count:
      layout.uplink_port_count == null
        ? null
        : Math.max(0, Math.min(128, layout.uplink_port_count)),
    main_port_count:
      layout.main_port_count == null
        ? null
        : Math.max(1, Math.min(128, layout.main_port_count)),
    slots_def: (layout.slots_def || []).map((slot) => {
      const groups = (slot.groups || []).map((g) => ({
        ...g,
        count: Math.max(1, Math.min(128, g.count || 1)),
      }))
      // 不提交已废弃的 port_count / port_types，避免与 groups 冲突触发校验
      return {
        groups,
        layout_x: slot.layout_x ?? null,
        layout_y: slot.layout_y ?? null,
        layout_w: slot.layout_w == null ? null : Math.max(20, Math.min(800, slot.layout_w)),
        layout_h: slot.layout_h == null ? null : Math.max(20, Math.min(800, slot.layout_h)),
        server_slot_kind: slot.server_slot_kind ?? null,
        orientation: slot.orientation ?? null,
        zone_label: slot.zone_label ?? null,
        zone_layout: slot.zone_layout ?? null,
      }
    }),
    ports: (layout.ports || []).map((port) => ({
      ...port,
      w: Math.max(8, Math.min(120, port.w ?? 12)),
      h: Math.max(8, Math.min(60, port.h ?? 10)),
    })),
  }
}

function toCanvasNodes(nodes: NetworkNode[]): CanvasNodeInput[] {
  return nodes.map((n) => {
    const port_layout = clampPortLayoutForApi(n.port_layout)
    // 有 port_layout.slots_def 时由后端派生 slots，避免前端陈旧 slots 先触发校验失败
    const slots =
      port_layout?.slots_def?.length
        ? null
        : n.kind === 'switch'
          ? null
          : (n.slots || []).slice(0, 8).map((s) => ({
              enabled: !!s.enabled && (s.port_count ?? 0) > 0,
              port_count: Math.max(0, Math.min(128, s.port_count ?? 1)),
            }))
    return {
      id: n.id,
      kind: n.kind,
      name: n.name,
      device_id: n.device_id,
      pos_x: n.pos_x,
      pos_y: n.pos_y,
      switch_port_count: Math.max(1, Math.min(128, n.switch_port_count || 48)),
      slots,
      port_layout,
    }
  })
}

function toCanvasLinks(links: NetworkLink[]): CanvasLinkInput[] {
  return links.map((l) => ({
    id: l.id,
    link_type: l.link_type,
    source_node_id: l.source_node_id,
    source_port: l.source_port,
    target_node_id: l.target_node_id,
    target_port: l.target_port,
    label: l.label,
  }))
}

export function useNetworkTopology() {
  const route = useRoute()
  const router = useRouter()

  const topologies = ref<NetworkTopology[]>([])
  const currentId = ref<string | null>(null)
  const nodes = ref<NetworkNode[]>([])
  const links = ref<NetworkLink[]>([])
  const loading = ref(false)
  const saving = ref(false)

  const currentTopology = computed(
    () => topologies.value.find((t) => t.id === currentId.value) || null,
  )

  function applyDetail(detail: Awaited<ReturnType<typeof getNetworkTopologyDetail>>) {
    currentId.value = detail.id
    nodes.value = detail.nodes.map((n) => ({ ...n, slots: n.slots || defaultSlots() }))
    links.value = detail.links
  }

  function setTopologyId(id: string | null) {
    const query = { ...route.query }
    if (id) query.topology_id = id
    else delete query.topology_id
    void router.replace({ query })
  }

  async function loadTopologies(preferId?: string | null) {
    const data = await listNetworkTopologies({ page_size: 100, sort: 'updated_at', order: 'desc' })
    topologies.value = data.items || []
    const queryId = preferId ?? (route.query.topology_id as string | undefined) ?? null
    const targetId =
      queryId && topologies.value.some((t) => t.id === queryId)
        ? queryId
        : topologies.value[0]?.id ?? null
    if (targetId) {
      await selectTopology(targetId, false)
    } else {
      currentId.value = null
      nodes.value = []
      links.value = []
    }
  }

  async function selectTopology(id: string, syncRoute = true) {
    loading.value = true
    try {
      const detail = await getNetworkTopologyDetail(id)
      applyDetail(detail)
      if (syncRoute) setTopologyId(id)
    } catch {
      ElMessage.error('加载拓扑失败')
    } finally {
      loading.value = false
    }
  }

  async function refreshCurrent() {
    if (!currentId.value) return
    await selectTopology(currentId.value, false)
  }

  async function saveCanvas() {
    if (!currentId.value) return false
    saving.value = true
    try {
      const detail = await saveNetworkCanvas(currentId.value, {
        nodes: toCanvasNodes(nodes.value),
        links: toCanvasLinks(links.value),
      })
      applyDetail(detail)
      ElMessage.success('保存成功')
      return true
    } catch (err: unknown) {
      const data = (err as { response?: { data?: { message?: string; details?: { errors?: Array<{ loc?: unknown[]; msg?: string }> } } } })
        ?.response?.data
      const first = data?.details?.errors?.[0]
      const loc = Array.isArray(first?.loc) ? first.loc.filter((x) => x !== 'body').join('.') : ''
      const detail = first?.msg ? `${loc ? `${loc}: ` : ''}${first.msg}` : ''
      ElMessage.error(detail || data?.message || '保存失败')
      return false
    } finally {
      saving.value = false
    }
  }

  async function createTopology(name: string, description?: string | null) {
    const created = await createNetworkTopology({
      name: name.trim(),
      description: description?.trim() || null,
    })
    await loadTopologies(created.id)
    return created
  }

  async function removeTopology() {
    if (!currentId.value) return
    await ElMessageBox.confirm('确定删除当前拓扑？', '提示', { type: 'warning' })
    await deleteNetworkTopology(currentId.value)
    currentId.value = null
    nodes.value = []
    links.value = []
    setTopologyId(null)
    await loadTopologies()
    ElMessage.success('已删除')
  }

  watch(
    () => route.query.topology_id,
    (id) => {
      if (typeof id === 'string' && id !== currentId.value && topologies.value.some((t) => t.id === id)) {
        void selectTopology(id, false)
      }
    },
  )

  return {
    topologies,
    currentId,
    currentTopology,
    nodes,
    links,
    loading,
    saving,
    loadTopologies,
    selectTopology,
    refreshCurrent,
    saveCanvas,
    createTopology,
    removeTopology,
    setTopologyId,
  }
}
