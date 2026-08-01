/** 运营大屏模块化布局配置（本地持久化） */

export type ScreenModuleId =
  | 'kpi'
  | 'util-gauge'
  | 'u-pie'
  | 'rack-top'
  | 'util-buckets'
  | 'device-type'
  | 'device-status'
  | 'power-room'
  | 'alert-racks'
  | 'network'
  | 'contract'

export type ScreenSpan = 1 | 2 | 3

export interface ScreenModuleDef {
  id: ScreenModuleId
  title: string
  description: string
  defaultSpan: ScreenSpan
  defaultEnabled: boolean
}

export interface ScreenModuleState {
  id: ScreenModuleId
  enabled: boolean
  span: ScreenSpan
  order: number
}

export type KpiKey =
  | 'datacenter_count'
  | 'room_count'
  | 'rack_count'
  | 'device_count'
  | 'mounted_device_count'
  | 'total_u'
  | 'free_u'
  | 'occupied_u'
  | 'utilization'
  | 'total_power'
  | 'mount_ratio'

export interface KpiOption {
  key: KpiKey
  label: string
  unit?: string
}

export type ScreenThemeId = 'teal' | 'cyan' | 'amber' | 'violet' | 'steel'

export interface ScreenThemeOption {
  id: ScreenThemeId
  label: string
  description: string
  preview: [string, string, string]
}

export const SCREEN_THEMES: ScreenThemeOption[] = [
  {
    id: 'teal',
    label: '青绿驾驶舱',
    description: '默认青绿科技风',
    preview: ['#06101a', '#1ec8a5', '#3aa0ff'],
  },
  {
    id: 'cyan',
    label: '深空青蓝',
    description: '冷色监控大屏',
    preview: ['#040b14', '#22d3ee', '#60a5fa'],
  },
  {
    id: 'amber',
    label: '琥珀运维',
    description: '暖色告警强调',
    preview: ['#120c08', '#f59e0b', '#fb7185'],
  },
  {
    id: 'violet',
    label: '紫晶智控',
    description: '高对比紫蓝主题',
    preview: ['#0b0616', '#a78bfa', '#38bdf8'],
  },
  {
    id: 'steel',
    label: '钢铁灰域',
    description: '低饱和工业风',
    preview: ['#0a0e12', '#94a3b8', '#38bdf8'],
  },
]

export interface ScreenLayoutConfig {
  version: 1
  title: string
  theme: ScreenThemeId
  refreshSec: number
  kpiKeys: KpiKey[]
  modules: ScreenModuleState[]
}

export const SCREEN_MODULE_DEFS: ScreenModuleDef[] = [
  {
    id: 'kpi',
    title: '核心指标',
    description: '可自定义的 KPI 卡片条',
    defaultSpan: 3,
    defaultEnabled: true,
  },
  {
    id: 'util-gauge',
    title: '整体利用率',
    description: '机柜 U 位占用仪表盘',
    defaultSpan: 1,
    defaultEnabled: true,
  },
  {
    id: 'u-pie',
    title: 'U 位构成',
    description: '已占用 / 空闲 U 位',
    defaultSpan: 1,
    defaultEnabled: true,
  },
  {
    id: 'rack-top',
    title: '机柜利用率 TOP',
    description: '按占用率排序的机柜条形图',
    defaultSpan: 1,
    defaultEnabled: true,
  },
  {
    id: 'util-buckets',
    title: '利用率分布',
    description: '机柜利用率区间统计',
    defaultSpan: 1,
    defaultEnabled: true,
  },
  {
    id: 'device-type',
    title: '设备类型分布',
    description: '按设备管理类型统计',
    defaultSpan: 1,
    defaultEnabled: true,
  },
  {
    id: 'device-status',
    title: '设备状态',
    description: '库存 / 上架 / 维护等',
    defaultSpan: 1,
    defaultEnabled: true,
  },
  {
    id: 'power-room',
    title: '机房功耗',
    description: '各机房设备功耗汇总',
    defaultSpan: 1,
    defaultEnabled: true,
  },
  {
    id: 'alert-racks',
    title: '高利用率告警',
    description: '利用率 ≥ 85% 的机柜',
    defaultSpan: 1,
    defaultEnabled: true,
  },
  {
    id: 'network',
    title: '网络设计',
    description: '项目 / 拓扑 / 节点 / 连线',
    defaultSpan: 1,
    defaultEnabled: true,
  },
  {
    id: 'contract',
    title: '合同采购',
    description: '合同数 / 采购量 / 已关联台账',
    defaultSpan: 1,
    defaultEnabled: true,
  },
]

export const KPI_OPTIONS: KpiOption[] = [
  { key: 'datacenter_count', label: '数据中心' },
  { key: 'room_count', label: '机房' },
  { key: 'rack_count', label: '机柜' },
  { key: 'device_count', label: '设备总数' },
  { key: 'mounted_device_count', label: '已上架' },
  { key: 'total_u', label: '总 U 位', unit: 'U' },
  { key: 'occupied_u', label: '已用 U', unit: 'U' },
  { key: 'free_u', label: '空闲 U', unit: 'U' },
  { key: 'utilization', label: '利用率', unit: '%' },
  { key: 'total_power', label: '总功耗', unit: 'W' },
  { key: 'mount_ratio', label: '上架率', unit: '%' },
]

const STORAGE_KEY = 'rackdcim.screen.layout.v1'

export function defaultScreenLayout(): ScreenLayoutConfig {
  return {
    version: 1,
    title: '智慧机房管理驾驶舱',
    theme: 'teal',
    refreshSec: 30,
    kpiKeys: [
      'datacenter_count',
      'room_count',
      'rack_count',
      'device_count',
      'mounted_device_count',
      'total_u',
      'free_u',
      'total_power',
    ],
    modules: SCREEN_MODULE_DEFS.map((def, index) => ({
      id: def.id,
      enabled: def.defaultEnabled,
      span: def.defaultSpan,
      order: index,
    })),
  }
}

function normalizeConfig(raw: Partial<ScreenLayoutConfig> | null): ScreenLayoutConfig {
  const base = defaultScreenLayout()
  if (!raw || raw.version !== 1) return base

  const byId = new Map((raw.modules || []).map((m) => [m.id, m]))
  const modules = SCREEN_MODULE_DEFS.map((def, index) => {
    const saved = byId.get(def.id)
    return {
      id: def.id,
      enabled: saved?.enabled ?? def.defaultEnabled,
      span: (saved?.span === 1 || saved?.span === 2 || saved?.span === 3
        ? saved.span
        : def.defaultSpan) as ScreenSpan,
      order: typeof saved?.order === 'number' ? saved.order : index,
    }
  }).sort((a, b) => a.order - b.order)

  const validKpi = new Set(KPI_OPTIONS.map((k) => k.key))
  const kpiKeys = (raw.kpiKeys || base.kpiKeys).filter((k): k is KpiKey =>
    validKpi.has(k as KpiKey),
  )
  const themeIds = new Set(SCREEN_THEMES.map((t) => t.id))
  const theme = themeIds.has(raw.theme as ScreenThemeId)
    ? (raw.theme as ScreenThemeId)
    : base.theme

  return {
    version: 1,
    title: (raw.title || base.title).trim() || base.title,
    theme,
    refreshSec: Math.min(300, Math.max(10, Number(raw.refreshSec) || base.refreshSec)),
    kpiKeys: kpiKeys.length ? kpiKeys : base.kpiKeys,
    modules,
  }
}

export function loadScreenLayout(): ScreenLayoutConfig {
  try {
    const text = localStorage.getItem(STORAGE_KEY)
    if (!text) return defaultScreenLayout()
    return normalizeConfig(JSON.parse(text) as Partial<ScreenLayoutConfig>)
  } catch {
    return defaultScreenLayout()
  }
}

export function saveScreenLayout(config: ScreenLayoutConfig) {
  const normalized = normalizeConfig(config)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized))
  return normalized
}

export function resetScreenLayout() {
  localStorage.removeItem(STORAGE_KEY)
  return defaultScreenLayout()
}

export function moduleDef(id: ScreenModuleId): ScreenModuleDef {
  return SCREEN_MODULE_DEFS.find((d) => d.id === id) || SCREEN_MODULE_DEFS[0]
}
