<script setup lang="ts">
import { computed } from 'vue'
import SwitchSquarePort from '@/components/SwitchSquarePort.vue'
import {
  SERVER_DEMO, groupServerPorts, normalizeDiskSize, normalizeServerFormFactor, rearDriveGrid,
  type ServerDiskSize, type ServerFormFactorU, type ServerPcieSlotAttr, type ServerPortAttr,
} from '@/utils/serverModelAttrs'

const props = withDefaults(defineProps<{
  heightU?: number
  psuCount?: number
  psuWatt?: number
  pcieSlotDefs?: ServerPcieSlotAttr[]
  diskCount?: number
  diskSize?: ServerDiskSize | string
  ports?: ServerPortAttr[]
  selectedPortId?: string | null
}>(), {
  heightU: 1, psuCount: 2, psuWatt: 800, pcieSlotDefs: () => [],
  diskCount: 0, diskSize: '2.5', ports: () => [],
})

const emit = defineEmits<{
  selectPort: [portId: string]
  inspectPort: [portId: string, ev: MouseEvent]
}>()

const u = computed<ServerFormFactorU>(() => normalizeServerFormFactor(props.heightU))
const psus = computed(() => Math.max(0, Math.min(8, Math.trunc(props.psuCount || 0))))
const pcieSlots = computed(() => (props.pcieSlotDefs || []).map((slot) => (
  u.value === 1 && slot.orientation !== 'horizontal'
    ? { ...slot, orientation: 'horizontal' as const }
    : slot
)))
type PlacedPcieSlot = ServerPcieSlotAttr & {
  layoutStyle: Record<string, string>
  autoPlaced: boolean
}

/** 在物理网格中为 PCIe 挡板做碰撞检测，指定区域满时自动使用最近空位。 */
const placedPcieSlots = computed<PlacedPcieSlot[]>(() => {
  const rows = u.value === 1 ? 3 : u.value === 2 ? 6 : 12
  const cols = 12
  const occupied = Array.from({ length: rows }, () => Array(cols).fill(false) as boolean[])
  const canPlace = (row: number, col: number, rowSpan: number, colSpan: number) => {
    if (row < 1 || col < 1 || row + rowSpan - 1 > rows || col + colSpan - 1 > cols) return false
    for (let r = row - 1; r < row - 1 + rowSpan; r++) {
      for (let c = col - 1; c < col - 1 + colSpan; c++) if (occupied[r][c]) return false
    }
    return true
  }
  const occupy = (row: number, col: number, rowSpan: number, colSpan: number) => {
    for (let r = row - 1; r < row - 1 + rowSpan; r++) {
      for (let c = col - 1; c < col - 1 + colSpan; c++) occupied[r][c] = true
    }
  }
  const slotsByArea = [...pcieSlots.value].sort((a, b) => {
    const aVertical = a.orientation === 'vertical' && u.value !== 1 ? 1 : 0
    const bVertical = b.orientation === 'vertical' && u.value !== 1 ? 1 : 0
    return bVertical - aVertical || a.index - b.index
  })
  const placed = slotsByArea.flatMap((slot) => {
    const vertical = slot.orientation === 'vertical' && u.value !== 1
    // 纵向长边固定占 6 行（约 2U），与横向挡板的长边保持同一物理尺度。
    const rowSpan = vertical ? Math.min(6, rows) : 1
    const colSpan = vertical ? 1 : 4
    const preferredRow = vertical
      ? slot.placement === 'top' ? 1 : slot.placement === 'bottom' ? rows - rowSpan + 1 : Math.floor((rows - rowSpan) / 2) + 1
      : slot.placement === 'top' ? 1 : slot.placement === 'bottom' ? rows : Math.ceil(rows / 2)
    const candidateRows = Array.from({ length: rows - rowSpan + 1 }, (_, index) => index + 1)
      .sort((a, b) => Math.abs(a - preferredRow) - Math.abs(b - preferredRow) || a - b)
    for (const row of candidateRows) {
      for (let col = 1; col <= cols - colSpan + 1; col++) {
        if (!canPlace(row, col, rowSpan, colSpan)) continue
        occupy(row, col, rowSpan, colSpan)
        return [{
          ...slot,
          autoPlaced: row !== preferredRow,
          layoutStyle: { gridColumn: `${col} / span ${colSpan}`, gridRow: `${row} / span ${rowSpan}` },
        }]
      }
    }
    // 兼容超出当前机箱物理容量的旧数据：不绘制越界或覆盖挡板。
    return []
  })
  return placed.sort((a, b) => a.index - b.index)
})
const grid = computed(() => rearDriveGrid(props.diskCount || 0, normalizeDiskSize(props.diskSize, '2.5')))
const groups = computed(() => groupServerPorts(props.ports || []))
const bmc = computed(() => groups.value.find((g) => g.kind === 'bmc')?.ports || [])
const ipmi = computed(() => groups.value.find((g) => g.kind === 'ipmi')?.ports || [])
const vga = computed(() => groups.value.find((g) => g.kind === 'vga')?.ports || [])
const usb = computed(() => groups.value.find((g) => g.kind === 'usb')?.ports || [])
const lom = computed(() => groups.value.find((g) => g.kind === 'lom')?.ports || [])
const frameStyle = computed(() => ({ aspectRatio: SERVER_DEMO.aspect(u.value) }))
const rearDiskStyle = computed(() => ({
  gridTemplateColumns: 'repeat(' + Math.max(1, grid.value.cols) + ', minmax(0, 1fr))',
  gridTemplateRows: 'repeat(' + Math.max(1, grid.value.rows) + ', minmax(0, 1fr))',
}))

function slotPorts(slotIndex: number) {
  return (props.ports || []).filter((p) => p.kind === 'flex' && p.slot_index === slotIndex)
}
function cardTitle(slot: ServerPcieSlotAttr) {
  if (slot.card_type === 'blank') return '空挡板'
  if (slot.card_type === 'raid') return 'RAID · ' + (slot.raid_level || 'raid1').toUpperCase()
  return (slot.card_type === 'nic_copper' ? 'RJ45' : 'SFP') + ' · ' + slot.speed.replace('ge', 'GE')
}
function onClick(id: string, ev: MouseEvent) {
  ev.preventDefault(); ev.stopPropagation(); emit('selectPort', id)
}
function onContext(id: string, ev: MouseEvent) {
  ev.preventDefault(); ev.stopPropagation(); emit('inspectPort', id, ev)
}
</script>

<template>
  <div class="srv-rear" :class="'u' + u" :style="frameStyle">
    <div class="rack-ear"><i /><i /><i /></div>
    <div class="rear-body">
      <div class="pcie-bay" :title="'PCIe 扩展区 · ' + pcieSlots.length + ' 个物理槽位'">
        <article
          v-for="slot in placedPcieSlots"
          :key="'pcie-' + slot.index"
          class="pcie-bracket"
          :class="[
            'card-' + slot.card_type,
            'orient-' + slot.orientation,
            'place-' + slot.placement,
            { occupied: slot.card_type !== 'blank', 'auto-placed': slot.autoPlaced },
          ]"
          :style="slot.layoutStyle"
          :title="'PCIe ' + slot.index + ' · ' + cardTitle(slot) + ' · ' + (slot.orientation === 'vertical' ? '竖向' : '横向') + (slot.autoPlaced ? ' · 指定区域已满，已自动避让' : '')"
        >
          <span class="mount-screw screw-a" /><span class="mount-screw screw-b" /><span class="bracket-lip" />
          <span class="slot-label">SLOT {{ slot.index }}</span>
          <span v-if="slot.card_type === 'blank'" class="blank-grid" aria-label="通风空挡板">
            <i v-for="n in 32" :key="n" />
          </span>
          <span v-else-if="slot.card_type === 'raid'" class="raid-board">
            <i class="raid-chip" /><i class="raid-heatsink" /><b>{{ (slot.raid_level || 'raid1').toUpperCase() }}</b>
          </span>
          <span v-else class="pcie-ports">
            <button
              v-for="p in slotPorts(slot.index)"
              :key="p.id" type="button" class="sq"
              :class="{ selected: selectedPortId === p.id }"
              :title="p.code + ' · ' + p.id"
              @click="onClick(p.id, $event)" @contextmenu="onContext(p.id, $event)"
            ><SwitchSquarePort :kind="p.iface_type === 'optical' ? 'optical' : 'copper'" :speed="p.speed" :label="p.code" /></button>
          </span>
          <span class="card-caption">{{ cardTitle(slot) }}</span>
        </article>
      </div>

      <div class="system-zone">
        <div v-for="n in (u === 1 ? 1 : 2)" :key="'fan-' + n" class="system-fan"><i /><span /></div>
        <div class="onboard-zone" title="板载与带外管理接口">
          <span class="onboard-label">ONBOARD / MGMT</span>
          <button v-for="p in vga" :key="p.id" type="button" class="vga" :class="{ selected: selectedPortId === p.id }" :title="p.code + ' · ' + p.id" @click="onClick(p.id, $event)" @contextmenu="onContext(p.id, $event)" />
          <button v-for="p in usb" :key="p.id" type="button" class="usb" :class="{ selected: selectedPortId === p.id }" :title="p.code + ' · ' + p.id" @click="onClick(p.id, $event)" @contextmenu="onContext(p.id, $event)">USB</button>
          <button v-for="p in [...bmc, ...ipmi, ...lom]" :key="p.id" type="button" class="sq onboard-port" :class="{ selected: selectedPortId === p.id }" :title="p.code + ' · ' + p.id" @click="onClick(p.id, $event)" @contextmenu="onContext(p.id, $event)">
            <SwitchSquarePort kind="copper" :label="p.code" />
          </button>
        </div>
      </div>

      <div v-if="!grid.empty" class="rear-disks" :style="rearDiskStyle">
        <div v-for="i in diskCount" :key="'rd-' + i" class="rdisk" :title="'后置盘 ' + i"><span /></div>
      </div>
      <div class="psu-col" :class="{ stacked: u >= 2 && psus > 1 }">
        <div v-for="i in psus" :key="'psu-' + i" class="psu" :title="'PSU ' + i + ' · ' + psuWatt + 'W'">
          <span class="psu-fan"><i /></span><span class="inlet" /><span class="led" />
        </div>
      </div>
    </div>
    <div class="rack-ear"><i /><i /><i /></div>
  </div>
</template>

<style scoped>
*{box-sizing:border-box}.srv-rear{container-type:inline-size;width:100%;max-width:860px;height:auto;display:flex;overflow:hidden;border:1px solid #61676e;border-radius:3px;background:linear-gradient(180deg,#e0e3e6 0%,#b6bcc2 42%,#8b9299 100%);box-shadow:inset 0 0 0 1px #f5f6f7,0 5px 14px rgba(24,31,38,.2)}
.rack-ear{width:13px;flex:0 0 13px;display:flex;flex-direction:column;justify-content:space-around;align-items:center;background:linear-gradient(90deg,#858c92,#d6dadd 45%,#767d84);border-right:1px solid #555c63}.rack-ear:last-child{border-right:0;border-left:1px solid #555c63}.rack-ear i{width:5px;height:5px;border-radius:50%;background:#202428;box-shadow:inset 0 0 0 1px #050607,0 0 0 1px #d9dde0}
.rear-body{flex:1;min-width:0;display:flex;gap:4px;padding:3px 4px;position:relative}.pcie-bay{--pcie-long:18.4cqw;--pcie-short:3.8cqw;flex:1 1 56%;min-width:0;display:grid;grid-template-columns:repeat(12,minmax(0,1fr));grid-template-rows:repeat(6,minmax(0,1fr));grid-auto-flow:row dense;place-items:center;gap:3px;padding:2px;overflow:hidden;border:1px solid #717981;background:linear-gradient(180deg,#9da4aa,#747c83);box-shadow:inset 0 0 0 1px rgba(255,255,255,.34)}
.pcie-bracket{position:relative;width:100%;height:100%;overflow:hidden;display:flex;align-items:center;justify-content:center;color:#20262b;border:1px solid #4e555b;border-radius:2px;background:linear-gradient(180deg,#d4d7d9,#979da2);box-shadow:inset 0 0 0 1px rgba(255,255,255,.52),0 1px 1px rgba(0,0,0,.25)}
.pcie-bracket.orient-horizontal,.pcie-bracket.orient-vertical{width:100%;min-width:0;max-width:100%;height:100%;min-height:0;max-height:100%;justify-self:stretch;align-self:stretch}.pcie-bracket.auto-placed{border-color:#b88619;box-shadow:inset 0 0 0 1px rgba(255,235,145,.72),0 1px 2px rgba(0,0,0,.28)}
.bracket-lip{position:absolute;left:0;right:0;top:0;height:2px;background:#eef0f1;border-bottom:1px solid #666d73}.mount-screw{position:absolute;z-index:3;width:4px;height:4px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#f2f2f2 0 20%,#646b70 28% 60%,#222 65%)}.screw-a{left:3px;top:3px}.screw-b{right:3px;bottom:3px}
.slot-label{position:absolute;z-index:4;top:3px;left:50%;transform:translateX(-50%);padding:0 3px;color:#20262b;background:rgba(235,237,238,.78);border-radius:2px;font:700 6px/1.35 Arial,sans-serif;white-space:nowrap}.orient-vertical .slot-label{top:50%;left:2px;transform:translateY(-50%);writing-mode:vertical-rl}.card-caption{position:absolute;right:3px;bottom:1px;z-index:4;color:#30363b;font:600 5px/1 Arial,sans-serif;white-space:nowrap}.orient-vertical .card-caption{display:none}
.blank-grid{width:88%;height:50%;display:grid;grid-template-columns:repeat(16,minmax(1px,1fr));grid-template-rows:repeat(2,minmax(2px,1fr));gap:1px;padding:2px 3px;border:1px solid #777e84;background:linear-gradient(180deg,#c1c5c8,#8f969b)}.blank-grid i{min-width:1px;min-height:2px;border-radius:1px;background:linear-gradient(180deg,#20262a,#555d62);box-shadow:inset 0 0 0 1px #171b1e}.orient-vertical .blank-grid{width:50%;height:88%;grid-template-columns:repeat(2,minmax(2px,1fr));grid-template-rows:repeat(16,minmax(1px,1fr));padding:3px 2px}
.pcie-bracket.occupied{background:linear-gradient(180deg,#b9bec2,#727a80)}.pcie-bracket.card-nic-copper{border-color:#9b6c2c}.pcie-bracket.card-nic-optical{border-color:#337a9d}.pcie-bracket.card-raid{border-color:#7f6b34}.raid-board{width:76%;height:52%;position:relative;display:flex;align-items:center;gap:4px;padding:2px 5px;background:linear-gradient(135deg,#315848,#18342a);border:1px solid #10251d;color:#f5cb57;font:700 6px Arial}.raid-chip{width:9px;height:9px;background:#151a1d;box-shadow:0 0 0 1px #6a7379}.raid-heatsink{flex:1;height:8px;background:repeating-linear-gradient(90deg,#9aa0a4 0 2px,#4c5257 2px 3px)}.orient-vertical .raid-board{width:58%;height:72%;flex-direction:column;padding:5px 2px}
.pcie-ports{display:flex;justify-content:center;align-items:center;gap:2px;width:80%;height:62%;padding:2px 5px;background:#343a3f;border:1px solid #171b1e}.orient-vertical .pcie-ports{width:62%;height:78%;flex-direction:column;padding:5px 2px}.sq{width:18px;height:18px;flex:0 0 18px;padding:0;border:0;background:transparent;cursor:pointer}.u1 .sq{width:14px;height:14px;flex-basis:14px}.sq.selected,.vga.selected,.usb.selected{outline:2px solid #409eff;outline-offset:1px}
.system-zone{flex:0 0 26%;min-width:86px;display:flex;flex-direction:column;justify-content:flex-end;gap:3px}.system-fan{flex:1;min-height:14px;position:relative;overflow:hidden;border:1px solid #555d63;background:repeating-radial-gradient(circle,#171b1f 0 2px,#555d62 3px 4px)}.system-fan i{position:absolute;inset:15%;border-radius:50%;background:conic-gradient(#171b1f 0 12%,#737a80 13% 24%,#171b1f 25% 37%,#737a80 38% 49%,#171b1f 50% 62%,#737a80 63% 74%,#171b1f 75% 87%,#737a80 88%)}.system-fan span{position:absolute;inset:42%;border-radius:50%;background:#20252a;border:1px solid #858c91}.u1 .system-fan{display:none}
.onboard-zone{min-height:24px;display:flex;align-items:flex-end;gap:2px;padding:9px 3px 2px;position:relative;border:1px solid #737a80;background:linear-gradient(180deg,#d0d3d5,#91979c)}.onboard-label{position:absolute;left:4px;top:2px;color:#465059;font:700 5px Arial;letter-spacing:.05em}.onboard-port{width:17px;height:17px;flex-basis:17px}.vga{width:18px;height:12px;border:0;background:#2767a5;clip-path:polygon(8% 0,92% 0,100% 28%,100% 100%,0 100%,0 28%);cursor:pointer}.usb{width:17px;height:9px;padding:0;border:1px solid #3a3d40;background:#17191b;color:#d6d6d6;font-size:4px;cursor:pointer}
.rear-disks{flex:0 0 18px;display:grid;gap:1px;align-self:stretch}.rdisk{display:flex;min-height:6px;padding:1px;border:1px solid #30353a;background:#111518}.rdisk span{flex:1;background:radial-gradient(#4c5358 .6px,transparent .7px);background-size:3px 3px}.psu-col{flex:0 0 11%;min-width:38px;display:flex;gap:2px}.psu-col.stacked{flex-direction:column}.psu{flex:1;min-width:0;display:grid;grid-template-columns:1fr 14px;grid-template-rows:1fr 7px;gap:2px;padding:2px;position:relative;border:1px solid #363c41;background:linear-gradient(135deg,#777e84,#343a3f)}.psu-fan{grid-row:1/3;display:flex;align-items:center;justify-content:center;border:1px solid #22282c;background:repeating-radial-gradient(circle,#161a1d 0 1px,#586067 2px 3px)}.psu-fan i{width:70%;aspect-ratio:1;border-radius:50%;background:conic-gradient(#15191c 0 18%,transparent 19% 24%,#15191c 25% 43%,transparent 44% 49%,#15191c 50% 68%,transparent 69% 74%,#15191c 75% 93%,transparent 94%)}.inlet{border:1px solid #171a1d;border-radius:1px;background:#0d0f11}.led{width:4px;height:4px;border-radius:50%;background:#54c761;box-shadow:0 0 3px #54c761;justify-self:end}
.u2 .rear-body{gap:6px;padding:5px 6px}.u2 .pcie-bay{flex-basis:58%;grid-template-columns:repeat(12,minmax(0,1fr));grid-template-rows:repeat(6,minmax(0,1fr));gap:4px;padding:4px}.u2 .system-zone{flex-basis:23%;gap:4px}.u2 .psu-col{flex-basis:12%;gap:6px;padding:2px 0}.u2 .psu{max-height:64px;padding:3px;grid-template-columns:1fr 16px;grid-template-rows:1fr 9px}.u1 .rear-body{gap:2px;padding:2px 3px}.u1 .pcie-bay{flex-basis:58%;grid-template-rows:repeat(3,minmax(0,1fr));gap:1px;padding:1px}.u1 .pcie-bracket.orient-horizontal{grid-column:span 6}.u1 .system-zone{flex-basis:25%;min-width:74px}.u1 .psu-col{min-width:54px;flex-basis:14%;flex-direction:row}.u1 .psu{grid-template-columns:1fr 8px}.u4 .pcie-bay{grid-template-rows:repeat(12,minmax(0,1fr))}.u4 .pcie-bracket.orient-horizontal{grid-column:span 4}.u4 .pcie-bracket.orient-vertical{grid-row:span 3}
</style>
