<script setup lang="ts">
import { computed } from 'vue'
import SwitchSquarePort from '@/components/SwitchSquarePort.vue'
import {
  normalizeSecurityFormFactor,
  securityDeviceProfile,
  securityPortId,
  type SecurityIfaceSlotAttr,
} from '@/utils/securityModelAttrs'

const props = withDefaults(defineProps<{
  subtype?: string
  heightU?: number
  slots?: SecurityIfaceSlotAttr[]
  cpuCores?: number
  memoryGb?: number
  diskCount?: number
  diskGb?: number
  throughputGbps?: number
  psuCount?: number
}>(), {
  subtype: 'firewall',
  heightU: 1,
  slots: () => [],
  cpuCores: 8,
  memoryGb: 32,
  diskCount: 2,
  diskGb: 480,
  throughputGbps: 10,
  psuCount: 2,
})

const emit = defineEmits<{ editSlot: [slotIndex: number] }>()
const profile = computed(() => securityDeviceProfile(props.subtype))
const height = computed(() => normalizeSecurityFormFactor(props.heightU))
const chassisStyle = computed(() => ({
  '--security-accent': profile.value.accent,
  aspectRatio: `482.6 / ${height.value * 44.45}`,
}))

type PortKind = '10g' | '1g' | 'control' | 'ha' | 'mgmt' | 'usb'
function ports(slot: SecurityIfaceSlotAttr, kind: PortKind, count: number) {
  return Array.from({ length: Math.max(0, count) }, (_, index) => ({
    id: securityPortId(slot.index, kind, index),
    label: `${kind.toUpperCase()}${index + 1}`,
    optical: kind === '10g' || kind === 'ha',
  }))
}
</script>

<template>
  <div class="security-sim" :class="[`u${height}`, `type-${subtype}`]" :style="chassisStyle" :data-panel-mode="profile.panelMode">
    <div class="rack-ear"><span /><span /><span /></div>
    <div class="security-body">
      <header class="security-brand">
        <span class="brand-mark">{{ profile.shortLabel }}</span>
        <span class="brand-name">{{ profile.label }} · {{ profile.hardwareTitle }}</span>
        <span class="status-led ok" /><span class="status-led" /><span class="status-led warn" />
      </header>
      <div class="security-content">
        <div class="air-intake"><span v-for="i in (height === 1 ? 18 : 32)" :key="i" /></div>
        <button v-for="slot in slots" :key="slot.index" type="button" class="interface-module" @click="emit('editSlot', slot.index)">
          <span class="module-title">SLOT {{ slot.index }}</span>
          <span class="module-ports">
            <span v-for="p in ports(slot, 'control', slot.control_count)" :key="p.id" class="port" :title="`${p.label} · ${p.id}`"><SwitchSquarePort kind="copper" :label="p.label" /></span>
            <span v-for="p in ports(slot, 'mgmt', slot.mgmt_count)" :key="p.id" class="port" :title="`${p.label} · ${p.id}`"><SwitchSquarePort kind="copper" :label="p.label" /></span>
            <span v-for="p in ports(slot, 'ha', slot.ha_count)" :key="p.id" class="port" :title="`${p.label} · ${p.id}`"><SwitchSquarePort kind="optical" :label="p.label" /></span>
            <span v-for="p in ports(slot, '1g', slot.ports_1g)" :key="p.id" class="port" :title="`${p.label} · ${p.id}`"><SwitchSquarePort kind="copper" :label="p.label" /></span>
            <span v-for="p in ports(slot, '10g', slot.ports_10g)" :key="p.id" class="port" :title="`${p.label} · ${p.id}`"><SwitchSquarePort kind="optical" :label="p.label" /></span>
            <span v-for="p in ports(slot, 'usb', slot.usb_count)" :key="p.id" class="usb-port" :title="`${p.label} · ${p.id}`">USB</span>
          </span>
        </button>
        <aside class="hardware-badge">
          <strong>{{ throughputGbps }}G</strong><span>{{ profile.throughputLabel }}</span>
          <small>{{ profile.processorLabel }} {{ cpuCores }}C · {{ memoryGb }}GB</small>
          <small>{{ profile.storageLabel }} {{ diskCount }}×{{ diskGb }}GB</small>
        </aside>
        <div class="front-control" title="前面板状态与维护区">
          <span class="front-model">{{ profile.shortLabel }}</span>
          <span class="front-power"><i /></span>
          <span class="front-usb">USB</span>
          <span class="front-console">CONSOLE</span>
        </div>
      </div>
      <footer class="security-footer">
        <span>{{ profile.deploymentMode }}</span>
        <span>双电源 ×{{ psuCount }}</span>
        <span>接口 ID 唯一可定位</span>
      </footer>
    </div>
    <div class="rack-ear"><span /><span /><span /></div>
  </div>
</template>

<style scoped>
.security-sim { width: 100%; max-width: 860px; height: auto; display: flex; overflow: hidden; border: 1px solid #313b46; border-radius: 3px; background: #161b20; box-shadow: inset 0 0 0 1px #69737e, 0 8px 20px rgba(0,0,0,.2); }
.rack-ear { width: 13px; flex: 0 0 13px; display: flex; flex-direction: column; justify-content: space-around; align-items: center; background: linear-gradient(90deg,#1d2228,#4b545e,#20262c); }
.rack-ear span { width: 5px; height: 5px; border-radius: 50%; background: #080a0c; box-shadow: inset 0 0 0 1px #69737e; }
.security-body { flex: 1; min-width: 0; display: flex; flex-direction: column; background: linear-gradient(180deg,#2a3138,#151a1f 65%,#0e1216); }
.security-brand { height: 18px; display: flex; align-items: center; gap: 7px; padding: 0 8px; border-bottom: 1px solid #06080a; color: #dce5ec; font-size: 8px; letter-spacing: .08em; }
.brand-mark { padding: 2px 6px; border-radius: 2px; background: var(--security-accent); color: white; font-weight: 800; }
.brand-name { margin-right: auto; opacity: .85; }
.status-led { width: 4px; height: 4px; border-radius: 50%; background: #65717b; }.status-led.ok{background:#3ed37a;box-shadow:0 0 5px #3ed37a}.status-led.warn{background:#f0ad3d}
.security-content { flex: 1; min-height: 0; display: flex; align-items: stretch; gap: 5px; padding: 4px 6px; }
.air-intake { width: 28px; display: grid; grid-template-columns: repeat(4,1fr); gap: 2px; padding: 3px; background: #10151a; border: 1px solid #3d4852; }
.air-intake span { border-radius: 50%; background: #050708; box-shadow: inset 0 0 0 1px #353d44; }
.interface-module { flex: 1 1 0; min-width: 0; overflow: hidden; display: flex; flex-direction: column; gap: 3px; padding: 3px; color: #b9c6d0; border: 1px solid #49545f; border-top: 2px solid var(--security-accent); background: linear-gradient(180deg,#303840,#1b2228); cursor: pointer; }
.interface-module:hover { border-color: var(--security-accent); box-shadow: 0 0 0 1px color-mix(in srgb,var(--security-accent) 40%,transparent); }
.module-title { font-size: 7px; text-align: left; opacity: .75; }.module-ports{display:flex;flex-wrap:wrap;align-content:flex-end;gap:2px;margin-top:auto}.port{width:16px;height:16px;display:inline-flex}.usb-port{font-size:5px;padding:2px;background:#1a1a1a;border:1px solid #7a7a7a;color:#ddd}
.hardware-badge { min-width: 68px; display: flex; flex-direction: column; justify-content: center; align-items: center; color: #c9d5dd; border-left: 1px solid #3a444d; font-size: 7px; }.hardware-badge strong{font-size:17px;color:var(--security-accent);line-height:1}.hardware-badge small{opacity:.7;margin-top:2px}
.security-footer { height: 14px; display: flex; justify-content: space-between; align-items: center; padding: 0 8px; color: #798691; font-size: 6px; border-top: 1px solid #303940; }
.u2 .security-brand{height:24px;font-size:10px}.u2 .security-content{padding:7px 8px;gap:8px}.u2 .port{width:19px;height:19px}.u2 .security-footer{height:18px;font-size:7px}
.type-optical_gate .security-body{background:linear-gradient(180deg,#29253b,#151426)}.type-database_audit .security-body,.type-net_audit .security-body,.type-host_audit .security-body{background:linear-gradient(180deg,#243732,#121c19)}
.interface-module{position:relative}.interface-module::before,.interface-module::after{content:"";position:absolute;width:4px;height:4px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#dce1e4 0 20%,#4d555c 28% 62%,#111 68%)}.interface-module::before{left:2px;top:2px}.interface-module::after{right:2px;bottom:2px}
.front-control{flex:0 0 74px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;padding:3px;border:1px solid #3d4852;background:linear-gradient(180deg,#303941,#171d22);color:#aebbc4;font:700 5px Arial}.front-model{width:100%;padding:2px;text-align:center;color:#fff;background:var(--security-accent)}.front-power{width:15px;aspect-ratio:1;border-radius:50%;background:radial-gradient(circle,#45d16c 0 22%,#1b2520 25% 52%,#707980 55% 70%,#171c20 72%)}.front-usb,.front-console{width:80%;padding:2px;text-align:center;border:1px solid #12171b;background:#080b0d}
[data-panel-mode="isolation"] .security-content{background:linear-gradient(90deg,transparent 0 49.5%,var(--security-accent) 49.5% 50%,transparent 50%)}[data-panel-mode="isolation"] .interface-module:nth-of-type(odd){border-top-color:#61a1f2}[data-panel-mode="isolation"] .interface-module:nth-of-type(even){border-top-color:#e47765}
[data-panel-mode="collector"] .hardware-badge{background:repeating-linear-gradient(180deg,#151c20 0 7px,#354149 8px 9px)}[data-panel-mode="sensor"] .air-intake{border-color:#b58a31}[data-panel-mode="cleaner"] .interface-module{box-shadow:inset 0 0 0 1px rgba(212,93,121,.25)}[data-panel-mode="crypto"] .hardware-badge{border:1px solid #735f92;background:#1d1925}
.u1 .front-control{flex-basis:56px;gap:1px;padding:2px}.u1 .front-power{width:10px}
</style>