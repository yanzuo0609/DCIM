/**
 * 布线场景引擎验收脚本（tsx）
 * 用法: npx tsx --tsconfig tsconfig.app.json scripts/wiring-scenario-fixtures.mts
 */
import { applyWiringRule, previewWiringPairs } from '../src/utils/wiringRuleApply.ts'
import {
  defaultWiringConfig,
  normalizeWiringConfig,
  applyConnectionTypeSideEffects,
} from '../src/utils/wiringTypes.ts'
import { annotatePortMediaAndInterface } from '../src/utils/wiringDeviceType.ts'

function mkPort(
  id: string,
  label: string,
  port_type: string,
  purpose: string,
  slot_index: number | null = null,
  extra: Record<string, unknown> = {},
) {
  return {
    id,
    label,
    port_type,
    purpose,
    slot_index,
    group_id: 'g1',
    reserved: false,
    peer_node_id: null,
    ...extra,
  }
}

function mkSwitch(
  id: string,
  name: string,
  opts: {
    subtype: 'gigabit' | 'ten_gigabit' | 'core' | 'aggregation'
    group: string
    role: string
    isBmc?: boolean
    downCount?: number
    upCount?: number
  },
) {
  const downType = opts.subtype === 'gigabit' ? '1g' : opts.subtype === 'ten_gigabit' ? '10g' : '10g'
  const down = opts.downCount ?? 8
  const up = opts.upCount ?? 4
  const ports = [
    ...Array.from({ length: down }, (_, i) =>
      mkPort(`${id}-d${i}`, String(i), downType, 'DOWNLINK', 1),
    ),
    ...Array.from({ length: up }, (_, i) =>
      mkPort(`${id}-u${i}`, `U${i + 1}`, opts.subtype === 'gigabit' ? '10g' : '40_100g', 'UPLINK', 2),
    ),
  ]
  annotatePortMediaAndInterface(ports as any)
  return {
    id,
    name,
    kind: 'switch',
    network_role: opts.role,
    device_group: opts.group,
    is_bmc_switch: !!opts.isBmc,
    on_canvas: true,
    port_layout: {
      switch_subtype: opts.subtype,
      ports,
      slots_def: [
        { groups: [{ id: 'g1', role: 'main' }] },
        { groups: [{ id: 'g2', role: 'uplink' }] },
      ],
    },
  }
}

function mkServer(id: string, name: string, group: string, slots10g = 2, portsPerSlot = 2) {
  const ports: any[] = []
  for (let s = 1; s <= slots10g; s++) {
    for (let i = 1; i <= portsPerSlot; i++) {
      ports.push(
        mkPort(`${id}-s${s}-10g${i}`, s === 1 ? `板载:10G-${i}` : `Slot${s}:10G-${i}`, '10g', 'SERVER', s),
      )
    }
  }
  ports.push(mkPort(`${id}-bmc`, '板载:IPMI-1', 'bmc', 'MGMT', 1))
  annotatePortMediaAndInterface(ports)
  return {
    id,
    name,
    kind: 'server',
    network_role: 'SERVER',
    device_group: group,
    on_canvas: true,
    port_layout: {
      ports,
      slots_def: Array.from({ length: slots10g }, () => ({
        groups: [{ id: 'g1', role: 'card' }],
      })),
    },
  }
}

function runCase(title: string, ruleCfg: Record<string, unknown>, nodes: any[]) {
  const cfg = normalizeWiringConfig(applyConnectionTypeSideEffects({ ...defaultWiringConfig(), ...ruleCfg }) as any)
  const rule = {
    id: 'r1',
    topology_id: 't1',
    name: title,
    enabled: true,
    mode: 'auto',
    config: cfg,
  } as any
  const { links, report } = applyWiringRule(rule, nodes, [])
  const perTarget: Record<string, number> = {}
  for (const n of nodes.filter((x) => x.kind === 'server' || x.network_role === 'ACCESS' || x.network_role === 'SERVER')) {
    perTarget[n.id] = links.filter((l) => l.target_node_id === n.id || l.source_node_id === n.id).length
  }
  console.log(
    `\n=== ${title} ===\n`,
    JSON.stringify(
      {
        scenario: report.scenario,
        created: report.created,
        ok: report.ok,
        issues: report.issues.map((i) => i.message),
        perTarget,
        sample: links.slice(0, 6).map((l) => `${l.source_label} -> ${l.target_label}`),
      },
      null,
      2,
    ),
  )
  return { links, report }
}

let failed = 0
function assert(cond: boolean, msg: string) {
  if (!cond) {
    console.error('FAIL:', msg)
    failed += 1
  } else {
    console.log('OK:', msg)
  }
}

// A2: 2×ACCESS_10G → 1×SERVER（2 slot）
{
  const nodes = [
    mkSwitch('sw1', '接入A', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS' }),
    mkSwitch('sw2', '接入B', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS' }),
    mkServer('srv1', '计算服务器1-srv1', '计算组', 2, 1),
  ]
  const { report, links } = runCase(
    'A2',
    {
      connection_type: 'ACCESS_ENDPOINT',
      source_groups: ['接入组'],
      target_groups: ['计算组'],
      link_count: 1,
      min_link_count: 1,
      max_link_count: 4,
    },
    nodes,
  )
  assert(report.scenario === 'A2', 'scenario A2')
  assert(links.length === 2, 'A2 creates 2 links')
  assert(report.ok, 'A2 ok')
}

// A3: 2×ACCESS → 4×SERVER，max_link=4 不得截断为 0
{
  const nodes = [
    mkSwitch('sw1', '接入A', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS' }),
    mkSwitch('sw2', '接入B', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS' }),
    mkServer('srv1', '计算服务器1-srv1', '计算组', 2, 1),
    mkServer('srv2', '计算服务器2-srv2', '计算组', 2, 1),
    mkServer('srv3', '计算服务器3-srv3', '计算组', 2, 1),
    mkServer('srv4', '计算服务器4-srv4', '计算组', 2, 1),
  ]
  const { report, links } = runCase(
    'A3-2x4',
    {
      connection_type: 'ACCESS_ENDPOINT',
      source_groups: ['接入组'],
      target_groups: ['计算组'],
      link_count: 1,
      min_link_count: 1,
      max_link_count: 4,
    },
    nodes,
  )
  assert(report.scenario === 'A3', 'scenario A3')
  assert(links.length === 8, `A3 creates 8 links (got ${links.length})`)
  for (const id of ['srv1', 'srv2', 'srv3', 'srv4']) {
    const n = links.filter((l) => l.target_node_id === id).length
    assert(n === 2, `${id} dual-home (=2, got ${n})`)
  }
  assert(report.ok, 'A3 ok')
}

// A3：不按设备数对齐；服务器口不足时尽力接入，容量看交换机下联口
{
  const nodes = [
    mkSwitch('sw1', '接入A', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS', downCount: 24 }),
    mkSwitch('sw2', '接入B', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS', downCount: 24 }),
    // 仅 1 个 10G 口：旧逻辑会报「不足以接入 2 台交换机」；新逻辑应接到 1 台并继续其它服务器
    mkServer('srv7', '计算服务器1-srv7', '计算组', 1, 1),
    mkServer('srv8', '计算服务器2-srv8', '计算组', 2, 1),
    mkServer('srv9', '计算服务器3-srv9', '计算组', 2, 1),
  ]
  const { report, links } = runCase(
    'A3-port-capacity',
    {
      connection_type: 'ACCESS_ENDPOINT',
      source_groups: ['接入组'],
      target_groups: ['计算组'],
      link_count: 1,
      min_link_count: 1,
      max_link_count: 64,
    },
    nodes,
  )
  assert(report.scenario === 'A3', 'A3 capacity scenario')
  assert(links.length >= 5, `A3 capacity ≥5 links (got ${links.length})`)
  assert(
    links.filter((l) => l.target_node_id === 'srv7').length === 1,
    'srv7 with 1 NIC gets 1 uplink (best-effort)',
  )
  assert(
    links.filter((l) => l.target_node_id === 'srv8').length === 2,
    'srv8 dual-home to both switches',
  )
  assert(
    !report.issues.some(
      (i) => i.level === 'error' && String(i.message).includes('不足以接入 2 台交换机'),
    ),
    'no hard error requiring NIC count == switch count',
  )
  assert(report.ok || links.length > 0, 'A3 capacity produces links')
}

// A3：服务器口误标 UPLINK + 规则残留 100G/UPLINK 目的口 → 仍应能接线
{
  const nodes = [
    mkSwitch('sw1', '接入A', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS', downCount: 8 }),
    mkSwitch('sw2', '接入B', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS', downCount: 8 }),
    mkServer('srv7', '计算服务器1-srv7', '计算组', 2, 2),
  ]
  for (const p of nodes[2].port_layout.ports) {
    p.purpose = 'UPLINK'
  }
  const { report, links } = runCase(
    'A3-mislabel-uplink',
    {
      connection_type: 'ACCESS_ENDPOINT',
      source_groups: ['接入组'],
      target_groups: ['计算组'],
      link_count: 1,
      target_port_purpose: 'UPLINK',
      target_port_pool: 'UPLINK',
      speed: '100G',
      port_speed: '100G',
      speed_mode: 'EXACT',
    },
    nodes,
  )
  assert(report.scenario === 'A2' || report.scenario === 'A3', `A3/A2 mislabel scenario (got ${report.scenario})`)
  assert(links.length >= 2, `A3 mislabel ≥2 links (got ${links.length})`)
  assert(
    !report.issues.some((i) => i.level === 'error' && String(i.message).includes('匹配 10G 口不足')),
    'no false insufficient 10G NIC error',
  )
  assert(report.ok, 'A3 mislabel ok')
}

// B1
{
  const nodes = [
    mkSwitch('bmc1', 'BMC交换机', {
      subtype: 'gigabit',
      group: 'BMC组',
      role: 'ACCESS',
      isBmc: true,
      downCount: 8,
    }),
    mkServer('srv1', 'srv1', '计算组', 1, 2),
    mkServer('srv2', 'srv2', '计算组', 1, 2),
  ]
  const { report, links } = runCase(
    'B1',
    {
      connection_type: 'BMC_ENDPOINT',
      source_groups: ['BMC组'],
      target_groups: ['计算组'],
      link_count: 1,
    },
    nodes,
  )
  assert(report.scenario === 'B1', 'scenario B1')
  assert(links.length === 2, 'B1 2 links')
  assert(
    links.every((l) => String(l.target_label).includes('IPMI')),
    'B1 only IPMI',
  )
}

// C2
{
  const nodes = [
    mkSwitch('c1', '核心A', { subtype: 'core', group: '核心组', role: 'CORE', downCount: 8, upCount: 4 }),
    mkSwitch('c2', '核心B', { subtype: 'core', group: '核心组', role: 'CORE', downCount: 8, upCount: 4 }),
    mkSwitch('a1', '接入1', {
      subtype: 'ten_gigabit',
      group: '接入单',
      role: 'ACCESS',
      downCount: 8,
      upCount: 6,
    }),
  ]
  const { report, links } = runCase(
    'C2',
    {
      connection_type: 'CORE_TO_ACCESS',
      source_groups: ['核心组'],
      target_groups: ['接入单'],
      link_count: 1,
      max_link_count: 4,
    },
    nodes,
  )
  assert(report.scenario === 'C2', 'scenario C2')
  assert(links.length === 2, `C2 2 uplinks (got ${links.length})`)
}

// C3: 2×CORE → 4×ACCESS；核心板卡口可被标成 UPLINK，仍应作 DOWNLINK 下联
{
  function mkCoreWithBoardUplinkStamp(id: string, name: string, group: string) {
    const ports = [
      // 36 口板卡，模型误标 UPLINK（非 U1 编号）— 应可作为 C 场景下联
      ...Array.from({ length: 36 }, (_, i) =>
        mkPort(`${id}-b${i}`, String(i + 1), '40_100g', 'UPLINK', 1),
      ),
      ...Array.from({ length: 4 }, (_, i) =>
        mkPort(`${id}-u${i}`, `U${i + 1}`, '40_100g', 'UPLINK', 2),
      ),
    ]
    annotatePortMediaAndInterface(ports as any)
    return {
      id,
      name,
      kind: 'switch',
      network_role: 'CORE',
      device_group: group,
      on_canvas: true,
      port_layout: {
        switch_subtype: 'core',
        ports,
        slots_def: [
          { groups: [{ id: 'g1', role: 'card' }] },
          { groups: [{ id: 'g2', role: 'uplink' }] },
        ],
      },
    }
  }
  const nodes = [
    mkCoreWithBoardUplinkStamp('c1', '核心A', '核心组'),
    mkCoreWithBoardUplinkStamp('c2', '核心B', '核心组'),
    mkSwitch('a1', '接入1', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS', upCount: 6 }),
    mkSwitch('a2', '接入2', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS', upCount: 6 }),
    mkSwitch('a3', '接入3', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS', upCount: 6 }),
    mkSwitch('a4', '接入4', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS', upCount: 6 }),
  ]
  const { report, links } = runCase(
    'C3-2x4',
    {
      connection_type: 'CORE_TO_ACCESS',
      source_groups: ['核心组'],
      target_groups: ['接入组'],
      link_count: 1,
      max_link_count: 4,
      speed: '100G',
      speed_mode: 'MIN',
    },
    nodes,
  )
  assert(report.scenario === 'C3', 'scenario C3')
  // 2 核心 × 4 接入 × 每对至少 1 条 = 8
  assert(links.length >= 8, `C3 full mesh ≥8 links (got ${links.length})`)
  for (const id of ['a1', 'a2', 'a3', 'a4']) {
    const toCore = links.filter(
      (l) =>
        (l.target_node_id === id || l.source_node_id === id) &&
        (l.source_node_id === 'c1' ||
          l.source_node_id === 'c2' ||
          l.target_node_id === 'c1' ||
          l.target_node_id === 'c2'),
    )
    const peers = new Set(
      toCore.map((l) => (l.source_node_id === id ? l.target_node_id : l.source_node_id)),
    )
    assert(peers.has('c1') && peers.has('c2'), `${id} must link to both cores (got ${[...peers]})`)
    assert(toCore.length >= 2, `${id} ≥2 uplinks to distinct cores (got ${toCore.length})`)
  }
  assert(report.ok, 'C3 ok')
}

// D1
{
  const nodes = [
    mkSwitch('a1', '接入A', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS' }),
    mkSwitch('a2', '接入B', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS' }),
  ]
  const { report, links } = runCase(
    'D1',
    {
      connection_type: 'SWITCH_INTERCONNECT',
      peer_link: true,
      source_groups: ['接入组'],
      source_role: 'ACCESS',
      link_count: 2,
    },
    nodes,
  )
  assert(report.scenario === 'D1', 'scenario D1')
  assert(links.length >= 2, `D1 at least 2 peer links (got ${links.length})`)
}

// --- V2 端口过滤 / 手动 ---
{
  const nodes = [
    mkSwitch('sw1', '接入A', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS', downCount: 8 }),
    mkServer('srv1', 'srv1', '计算组', 1, 4),
  ]
  // 混入 1G 业务口，EXACT 10G 不应选用
  nodes[1].port_layout.ports.push(
    mkPort('srv1-1g1', '板载:1G-1', '1g', 'SERVER', 1),
  )
  annotatePortMediaAndInterface(nodes[1].port_layout.ports)

  const { report, links } = runCase(
    'range-1-4',
    {
      connection_type: 'ACCESS_ENDPOINT',
      source_groups: ['接入组'],
      target_groups: ['计算组'],
      link_count: 2,
      source_port_range: '1-4',
      speed: '10G',
      speed_mode: 'EXACT',
      allocation_mode: 'AUTO',
    },
    nodes,
  )
  assert(report.scenario === 'A1', 'range scenario A1')
  assert(links.length === 2, `range creates 2 (got ${links.length})`)
  assert(
    links.every((l) => {
      const sn = Number(String(l.source_label).split(':').pop()?.replace(/\D/g, ''))
      return sn >= 1 && sn <= 4
    }),
    'source ports only in range 1-4',
  )
  assert(
    links.every((l) => !String(l.target_label).includes('1G')),
    'EXACT 10G skips 1G ports',
  )
}

{
  const nodes = [
    mkSwitch('sw1', '接入A', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS' }),
    mkServer('srv1', 'srv1', '计算组', 1, 2),
  ]
  const cfg = normalizeWiringConfig(
    applyConnectionTypeSideEffects({
      ...defaultWiringConfig(),
      connection_type: 'ACCESS_ENDPOINT',
      source_groups: ['接入组'],
      target_groups: ['计算组'],
      link_count: 1,
      allocation_mode: 'MANUAL',
      pairs: [
        {
          source_node_id: 'sw1',
          source_port_id: 'sw1-d3',
          target_node_id: 'srv1',
          target_port_id: 'srv1-s1-10g2',
        },
        {
          source_node_id: 'sw1',
          source_port_id: 'sw1-d5',
          target_node_id: 'srv1',
          target_port_id: 'srv1-s1-10g1',
        },
      ],
    }) as any,
  )
  const rule = {
    id: 'r-manual',
    topology_id: 't1',
    name: 'manual-pairs',
    enabled: true,
    mode: 'manual',
    config: cfg,
  } as any
  const { links, report } = applyWiringRule(rule, nodes, [])
  console.log('\n=== manual-pairs ===\n', JSON.stringify({ created: report.created, sample: links.map((l) => `${l.source_label}->${l.target_label}`) }, null, 2))
  assert(links.length === 2, 'MANUAL creates exactly 2')
  assert(links.every((l) => l.source_port === 'sw1-d3' || l.source_port === 'sw1-d5'), 'MANUAL uses specified source ports')
}

{
  const nodes = [
    mkSwitch('sw1', '接入A', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS' }),
    mkServer('srv1', 'srv1', '计算组', 1, 2),
  ]
  const cfg = normalizeWiringConfig(
    applyConnectionTypeSideEffects({
      ...defaultWiringConfig(),
      connection_type: 'ACCESS_ENDPOINT',
      source_groups: ['接入组'],
      target_groups: ['计算组'],
      link_count: 1,
      allocation_mode: 'HYBRID',
    }) as any,
  )
  const rule = {
    id: 'r-hyb',
    topology_id: 't1',
    name: 'hybrid',
    enabled: true,
    mode: 'auto',
    config: cfg,
  } as any
  const preview = previewWiringPairs(rule, nodes, [])
  assert(preview.pairs.length >= 1, `HYBRID preview has pairs (got ${preview.pairs.length})`)
  // 改目标口后手动应用
  const alt = nodes[1].port_layout.ports.find((p: any) => p.id !== preview.pairs[0].target_port_id && p.purpose === 'SERVER')
  const pairs = [
    {
      ...preview.pairs[0],
      target_port_id: alt?.id || preview.pairs[0].target_port_id,
    },
  ]
  const applied = applyWiringRule(
    {
      ...rule,
      mode: 'manual',
      config: { ...cfg, allocation_mode: 'MANUAL', pairs },
    },
    nodes,
    [],
  )
  assert(applied.links.length === 1, 'HYBRID edited pair applies 1 link')
  assert(
    applied.links[0].target_port === pairs[0].target_port_id,
    'HYBRID uses manually edited target port',
  )
}

{
  // 组/手选优先于角色：默认或残留角色不应把源匹配打成 0；源组可对目标手选
  const nodes = [
    mkSwitch('c1', '核心1', {
      subtype: 'core',
      group: '核心组',
      role: 'CORE',
      downCount: 16,
      upCount: 4,
    }),
    mkSwitch('c2', '核心2', {
      subtype: 'core',
      group: '核心组',
      role: 'CORE',
      downCount: 16,
      upCount: 4,
    }),
    mkSwitch('a1', '接入1', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS', upCount: 6 }),
    mkSwitch('a2', '接入2', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS', upCount: 6 }),
    mkSwitch('a3', '接入3', { subtype: 'ten_gigabit', group: '接入组', role: 'ACCESS', upCount: 6 }),
  ]
  // 给核心板卡口打成可作下联的 40/100G
  for (const n of nodes.filter((x) => x.id.startsWith('c'))) {
    for (const p of n.port_layout.ports) {
      if (p.purpose === 'DOWNLINK') {
        ;(p as any).port_type = '40_100g'
        ;(p as any).group_id = 'card1'
      }
    }
    annotatePortMediaAndInterface(n.port_layout.ports as any)
  }
  const cfg = normalizeWiringConfig({
    ...defaultWiringConfig(),
    connection_type: 'CORE_TO_ACCESS',
    source_role: 'ACCESS', // 残留错误角色，有源组时应忽略
    source_groups: ['核心组'],
    source_node_ids: [],
    target_role: 'CORE', // 残留错误角色，有手选时应忽略
    target_groups: [],
    target_node_ids: ['a1', 'a2', 'a3'],
    link_count: 1,
    allocation_mode: 'AUTO',
  } as any)
  const rule = {
    id: 'r-mix-match',
    topology_id: 't1',
    name: 'group-to-manual',
    enabled: true,
    mode: 'auto',
    config: cfg,
  } as any
  const { links, report } = applyWiringRule(rule, nodes as any, [])
  console.log(
    '\n=== mix group↔manual ===\n',
    JSON.stringify(
      { created: report.created, matched: [report.matched_sources, report.matched_targets], ok: report.ok },
      null,
      2,
    ),
  )
  assert(report.matched_sources === 2, `mix: sources=2 (got ${report.matched_sources})`)
  assert(report.matched_targets === 3, `mix: targets=3 (got ${report.matched_targets})`)
  assert(report.ok && links.length >= 6, `mix: full mesh ≥6 (got ${links.length})`)
}

console.log(failed ? `\n${failed} assertion(s) failed` : '\nAll fixtures passed')
process.exit(failed ? 1 : 0)
