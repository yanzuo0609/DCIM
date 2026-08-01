export interface RackUsagePreset {
  id: string
  label: string
  color: string
}

const STORAGE_KEY = 'dcim.rackUsagePresets.v1'

export const DEFAULT_USAGE_PRESETS: RackUsagePreset[] = [
  { id: 'biz', label: '业务应用', color: '#FFE566' },
  { id: 'mgmt', label: '管理网', color: '#B3D8FF' },
  { id: 'storage', label: '存储', color: '#C2E7B0' },
  { id: 'security', label: '安全', color: '#FBC4C4' },
  { id: 'network', label: '网络', color: '#D3C6F0' },
  { id: 'test', label: '测试', color: '#FFE0B2' },
]

export function loadUsagePresets(): RackUsagePreset[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_USAGE_PRESETS.map((p) => ({ ...p }))
    const parsed = JSON.parse(raw) as RackUsagePreset[]
    if (!Array.isArray(parsed) || !parsed.length) {
      return DEFAULT_USAGE_PRESETS.map((p) => ({ ...p }))
    }
    return parsed
      .filter((p) => p && typeof p.label === 'string' && typeof p.color === 'string')
      .map((p, idx) => ({
        id: p.id || `custom-${idx}`,
        label: p.label.trim() || `用途${idx + 1}`,
        color: p.color,
      }))
  } catch {
    return DEFAULT_USAGE_PRESETS.map((p) => ({ ...p }))
  }
}

export function saveUsagePresets(presets: RackUsagePreset[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(presets))
}
