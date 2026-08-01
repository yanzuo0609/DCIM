/** 3D 仿真：自定义场景模型（本地库） */

export type CustomSceneModel = {
  id: string
  name: string
  color: string
}

const STORAGE_KEY = 'dcim.scene.customModels.v1'

const DEFAULT_COLORS = ['#5a7a9a', '#3d8b6e', '#8b6b3d', '#6b5a8b', '#8b4a5a', '#4a7a8b']

export function loadCustomSceneModels(): CustomSceneModel[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed
      .map((item) => {
        if (!item || typeof item !== 'object') return null
        const obj = item as Record<string, unknown>
        const id = typeof obj.id === 'string' ? obj.id : ''
        const name = typeof obj.name === 'string' ? obj.name.trim() : ''
        const color = typeof obj.color === 'string' ? obj.color : '#5a7a9a'
        if (!id || !name) return null
        return { id, name: name.slice(0, 20), color }
      })
      .filter((x): x is CustomSceneModel => !!x)
  } catch {
    return []
  }
}

export function saveCustomSceneModels(models: CustomSceneModel[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(models))
}

export function createCustomSceneModel(name: string, color?: string): CustomSceneModel {
  const trimmed = name.trim().slice(0, 20) || '自定义模型'
  const list = loadCustomSceneModels()
  const model: CustomSceneModel = {
    id: `cm_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`,
    name: trimmed,
    color: color || DEFAULT_COLORS[list.length % DEFAULT_COLORS.length],
  }
  list.push(model)
  saveCustomSceneModels(list)
  return model
}

export function removeCustomSceneModel(id: string): CustomSceneModel[] {
  const next = loadCustomSceneModels().filter((m) => m.id !== id)
  saveCustomSceneModels(next)
  return next
}

export function updateCustomSceneModel(
  id: string,
  patch: Partial<Pick<CustomSceneModel, 'name' | 'color'>>,
): CustomSceneModel[] {
  const list = loadCustomSceneModels().map((m) => {
    if (m.id !== id) return m
    return {
      ...m,
      name: patch.name != null ? patch.name.trim().slice(0, 20) || m.name : m.name,
      color: patch.color || m.color,
    }
  })
  saveCustomSceneModels(list)
  return list
}
