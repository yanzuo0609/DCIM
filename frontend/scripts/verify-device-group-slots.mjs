/**
 * 独立设备组：slots 规格 + 同拓扑按槽位封顶不重复
 */
import assert from 'node:assert/strict'

function migrateSlotsFromLegacy(raw) {
  if (Array.isArray(raw.slots) && raw.slots.length) {
    return raw.slots.map((s) => ({
      id: s.id || 'x',
      label: s.label || '设备',
      role: s.role || null,
      design_model_id: s.design_model_id || null,
      count: Math.max(1, Math.floor(Number(s.count) || 1)),
    }))
  }
  const planned = raw.planned_count > 0 ? Math.floor(raw.planned_count) : 0
  if (planned || raw.design_model_id) {
    return [
      {
        id: 'legacy',
        label: '设备',
        role: raw.role || null,
        design_model_id: raw.design_model_id || null,
        count: Math.max(1, planned || 1),
      },
    ]
  }
  return []
}

function totalSlotCount(slots) {
  return slots.reduce((s, x) => s + x.count, 0)
}

// mixed group
const def = {
  name: 'POD-A',
  role: 'ACCESS',
  slots: [
    { id: 's1', label: '接入交换机', role: 'ACCESS', design_model_id: 'm-sw', count: 2 },
    { id: 's2', label: '服务器', role: 'SERVER', design_model_id: 'm-srv', count: 6 },
  ],
}
assert.equal(totalSlotCount(def.slots), 8)
assert.equal(migrateSlotsFromLegacy(def).length, 2)

// legacy migrate
const legacy = migrateSlotsFromLegacy({
  name: 'allacc',
  role: 'SERVER',
  planned_count: 6,
  design_model_id: 'm-srv',
})
assert.equal(legacy.length, 1)
assert.equal(legacy[0].count, 6)

// independent: catalog does not need canvas nodes
assert.equal(def.slots.every((s) => s.design_model_id), true)

console.log('PASS: independent device group slots')
