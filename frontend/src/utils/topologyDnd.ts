/** 从模型库拖入：值为 design model id */
export const TOPOLOGY_DND_MIME = 'application/x-dcim-node-id'

/** 从设备组列表拖入：JSON TopologyGroupDragPayload */
export const TOPOLOGY_GROUP_DND_MIME = 'application/x-dcim-device-group'

export interface TopologyGroupDragPayload {
  name: string
}

export function setDeviceGroupDragData(dt: DataTransfer, payload: TopologyGroupDragPayload) {
  const raw = JSON.stringify(payload)
  dt.setData(TOPOLOGY_GROUP_DND_MIME, raw)
  dt.setData('text/plain', `group:${payload.name}`)
  dt.effectAllowed = 'copy'
}

export function readDeviceGroupDragData(dt: DataTransfer | null): TopologyGroupDragPayload | null {
  if (!dt) return null
  const raw = dt.getData(TOPOLOGY_GROUP_DND_MIME)
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as TopologyGroupDragPayload
      if (parsed?.name) return { name: String(parsed.name) }
    } catch {
      /* ignore */
    }
  }
  const plain = dt.getData('text/plain') || ''
  if (plain.startsWith('group:')) {
    const name = plain.slice('group:'.length).trim()
    if (name) return { name }
  }
  return null
}

export function setDesignModelDragData(dt: DataTransfer, modelId: string) {
  dt.setData(TOPOLOGY_DND_MIME, modelId)
  dt.setData('text/plain', modelId)
  dt.effectAllowed = 'copy'
}
