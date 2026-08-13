import assert from 'node:assert/strict'

const SEP = '::'
function subgroupRef(group, slotId) {
  return `${group}${SEP}${slotId}`
}
function parseSubgroupRef(ref) {
  const i = ref.indexOf(SEP)
  if (i <= 0) return null
  return { groupName: ref.slice(0, i), slotId: ref.slice(i + 2) }
}
function parentGroupNamesFromRefs(refs) {
  return [...new Set(refs.map((r) => parseSubgroupRef(r)?.groupName || r))]
}

const r = subgroupRef('POD-A', 'slot-sw')
assert.equal(r, 'POD-A::slot-sw')
assert.deepEqual(parseSubgroupRef(r), { groupName: 'POD-A', slotId: 'slot-sw' })
assert.deepEqual(parentGroupNamesFromRefs(['POD-A', 'POD-A::slot-sw', 'SER::s1']), [
  'POD-A',
  'SER',
])

// matching: node has parent + subgroup tags
const nodeGroups = ['POD-A', 'POD-A::slot-sw']
assert.ok(nodeGroups.includes('POD-A'))
assert.ok(nodeGroups.includes('POD-A::slot-sw'))
assert.ok(!nodeGroups.includes('POD-A::slot-srv'))

console.log('PASS: subgroup refs')
