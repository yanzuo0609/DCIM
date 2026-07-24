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

function toCanvasNodes(nodes: NetworkNode[]): CanvasNodeInput[] {
  return nodes.map((n) => ({
    id: n.id,
    kind: n.kind,
    name: n.name,
    device_id: n.device_id,
    pos_x: n.pos_x,
    pos_y: n.pos_y,
    switch_port_count: n.switch_port_count,
    slots: n.kind === 'switch' ? null : n.slots,
    port_layout: n.port_layout || null,
  }))
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
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      ElMessage.error(msg || '保存失败')
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
