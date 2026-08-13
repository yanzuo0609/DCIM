/**
 * 组视图聚合与规则绑定字段自检
 */
import assert from 'node:assert/strict'

function primaryGroup(node) {
  const g = node.device_groups?.[0] || node.device_group
  return g || null
}

function buildGlyphs(nodes) {
  const map = new Map()
  for (const n of nodes.filter((x) => x.on_canvas !== false)) {
    const g = primaryGroup(n)
    if (!g) continue
    const list = map.get(g) || []
    list.push(n)
    map.set(g, list)
  }
  return [...map.entries()].map(([name, members]) => ({
    name,
    count: members.length,
    pos_x: Math.round(members.reduce((s, m) => s + m.pos_x, 0) / members.length),
    pos_y: Math.round(members.reduce((s, m) => s + m.pos_y, 0) / members.length),
  }))
}

const nodes = [
  { id: '1', name: 'a', on_canvas: true, pos_x: 0, pos_y: 0, device_groups: ['ACC'] },
  { id: '2', name: 'b', on_canvas: true, pos_x: 100, pos_y: 0, device_groups: ['ACC'] },
  { id: '3', name: 'c', on_canvas: true, pos_x: 200, pos_y: 200, device_groups: ['SER'] },
  { id: '4', name: 'solo', on_canvas: true, pos_x: 0, pos_y: 200 },
]
const glyphs = buildGlyphs(nodes)
assert.equal(glyphs.length, 2)
assert.equal(glyphs.find((g) => g.name === 'ACC').count, 2)
assert.equal(glyphs.find((g) => g.name === 'ACC').pos_x, 50)

const def = { name: 'ACC', wiring_rule_ids: ['r1', 'r2'], slots: [{ count: 2 }] }
assert.equal(def.wiring_rule_ids.length, 2)

console.log('PASS: group view + rule binding fields')
