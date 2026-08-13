/**
 * 端口介质类型目录（内置 + 用户新建）
 * 存 localStorage，供布线规则「端口介质」下拉使用。
 */

export interface PortMediaTypeDef {
  /** 稳定键：内置用 LC_LC/MPO8…；自定义用 slug */
  value: string
  label: string
  /** 粗分：过滤端口 media */
  physical: 'AUTO' | 'FIBER' | 'COPPER'
  /** 写入规则 connector 的提示值 */
  connector?: string | null
  /** 芯数（MPO） */
  fiber_cores?: number | null
  builtin?: boolean
}

const STORAGE_KEY = 'dcim.portMediaTypes'

export const PORT_MEDIA_BUILTIN: PortMediaTypeDef[] = [
  { value: 'AUTO', label: '不限', physical: 'AUTO', builtin: true },
  {
    value: 'LC_LC',
    label: 'LC-LC光纤接口',
    physical: 'FIBER',
    connector: 'LC',
    fiber_cores: 2,
    builtin: true,
  },
  {
    value: 'MPO8',
    label: 'MPO8芯光纤',
    physical: 'FIBER',
    connector: 'MPO',
    fiber_cores: 8,
    builtin: true,
  },
  {
    value: 'MPO4',
    label: 'MPO4芯光纤',
    physical: 'FIBER',
    connector: 'MPO',
    fiber_cores: 4,
    builtin: true,
  },
]

function slugify(label: string): string {
  const base = String(label || '')
    .trim()
    .replace(/\s+/g, '_')
    .replace(/[^\w\u4e00-\u9fff\-]+/g, '')
  return base || `CUSTOM_${Date.now().toString(36)}`
}

function loadCustomRaw(): PortMediaTypeDef[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const list = JSON.parse(raw) as PortMediaTypeDef[]
    if (!Array.isArray(list)) return []
    return list
      .filter((x) => x && x.value && x.label)
      .map((x) => ({
        value: String(x.value),
        label: String(x.label),
        physical: x.physical === 'COPPER' ? 'COPPER' : x.physical === 'AUTO' ? 'AUTO' : 'FIBER',
        connector: x.connector ?? null,
        fiber_cores: x.fiber_cores ?? null,
        builtin: false,
      }))
  } catch {
    return []
  }
}

function saveCustom(list: PortMediaTypeDef[]) {
  const customs = list.filter((x) => !x.builtin)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(customs))
}

/** 内置 + 自定义 */
export function listPortMediaTypes(): PortMediaTypeDef[] {
  const customs = loadCustomRaw()
  const builtinVals = new Set(PORT_MEDIA_BUILTIN.map((b) => b.value))
  const merged = [...PORT_MEDIA_BUILTIN]
  for (const c of customs) {
    if (builtinVals.has(c.value)) continue
    if (merged.some((m) => m.value === c.value || m.label === c.label)) continue
    merged.push(c)
  }
  return merged
}

export function findPortMediaType(value: string | null | undefined): PortMediaTypeDef | null {
  if (!value) return null
  return listPortMediaTypes().find((x) => x.value === value || x.label === value) || null
}

/** 新建自定义介质；返回写入后的定义 */
export function addCustomPortMediaType(
  label: string,
  opts?: { physical?: 'FIBER' | 'COPPER'; connector?: string | null },
): PortMediaTypeDef {
  const name = String(label || '').trim()
  if (!name) throw new Error('介质名称不能为空')
  const existing = listPortMediaTypes()
  if (existing.some((x) => x.label === name || x.value === name)) {
    throw new Error('介质类型已存在')
  }
  const def: PortMediaTypeDef = {
    value: `CUSTOM_${slugify(name)}`,
    label: name,
    physical: opts?.physical || 'FIBER',
    connector: opts?.connector ?? null,
    fiber_cores: null,
    builtin: false,
  }
  const customs = loadCustomRaw()
  customs.push(def)
  saveCustom(customs)
  return def
}

export function removeCustomPortMediaType(value: string): boolean {
  const customs = loadCustomRaw().filter((x) => x.value !== value)
  if (customs.length === loadCustomRaw().length) return false
  saveCustom(customs)
  return true
}

/** 选中介质时同步规则上的 connector / 线缆粗分提示 */
export function applyPortMediaToRuleConfig(cfg: {
  port_media?: string | null
  connector?: string | null
  media?: string | null
}): void {
  const def = findPortMediaType(cfg.port_media)
  if (!def || def.value === 'AUTO') return
  if (def.connector) cfg.connector = def.connector
  if (def.physical === 'FIBER' && (!cfg.media || cfg.media === 'AUTO')) {
    cfg.media = def.connector === 'MPO' ? 'MPO' : 'FIBER_MM'
  }
  if (def.physical === 'COPPER' && (!cfg.media || cfg.media === 'AUTO')) {
    cfg.media = 'COPPER'
  }
}
