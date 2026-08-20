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
  fanCount?: number
  psuCount?: number
}>(), {
  subtype: 'firewall',
  heightU: 1,
  slots: () => [],
  fanCount: 2,
  psuCount: 2,
})

const emit = defineEmits<{ editSlot: [slotIndex: number] }>()
const profile = computed(() => securityDeviceProfile(props.subtype))
const height = computed(() => normalizeSecurityFormFactor(props.heightU))
const fans = computed(() => Math.max(0, Math.min(16, Math.trunc(props.fanCount || profile.value.fanCount))))
const psus = computed(() => Math.max(1, Math.min(8, Math.trunc(props.psuCount || 2))))
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
  <div class="security-rear" :class="[`u${height}`, `type-${subtype}`]" :style="chassisStyle" :data-panel-mode="profile.panelMode">
    <div class="rack-ear"><i /><i /><i /></div>
    <div class="rear-shell">
      <header class="rear-header">
        <b>{{ profile.shortLabel }} · REAR I/O</b>
        <span>{{ profile.hardwareTitle }}</span>
        <i class="status-led" />
      </header>
      <div class="rear-content">
        <section class="psu-bank" title="热插拔冗余电源">
          <article v-for="i in psus" :key="`security-rear-psu-${i}`" class="psu-module">
            <span class="psu-fan"><i /></span>
            <span class="iec-inlet"><i /><i /><i /></span>
            <span class="psu-led" />
            <b>PSU {{ i }}</b>
          </article>
        </section>
        <section class="fan-bank" title="可热插拔风扇墙">
          <article v-for="i in fans" :key="`security-rear-fan-${i}`" class="fan-module">
            <span class="fan-rotor"><i /></span><b>F{{ i }}</b>
          </article>
        </section>
        <section class="rear-io-bank">
          <button v-for="slot in slots" :key="`rear-slot-${slot.index}`" type="button" class="rear-slot" @click="emit('editSlot', slot.index)">
            <span class="rear-slot-title">SLOT {{ slot.index }}</span>
            <span class="rear-slot-ports">
              <span v-for="p in ports(slot, 'control', slot.control_count)" :key="p.id" class="port" :title="`${p.label} · ${p.id}`"><SwitchSquarePort kind="copper" :label="p.label" /></span>
              <span v-for="p in ports(slot, 'mgmt', slot.mgmt_count)" :key="p.id" class="port" :title="`${p.label} · ${p.id}`"><SwitchSquarePort kind="copper" :label="p.label" /></span>
              <span v-for="p in ports(slot, 'ha', slot.ha_count)" :key="p.id" class="port" :title="`${p.label} · ${p.id}`"><SwitchSquarePort kind="optical" :label="p.label" /></span>
              <span v-for="p in ports(slot, '1g', slot.ports_1g)" :key="p.id" class="port" :title="`${p.label} · ${p.id}`"><SwitchSquarePort kind="copper" :label="p.label" /></span>
              <span v-for="p in ports(slot, '10g', slot.ports_10g)" :key="p.id" class="port" :title="`${p.label} · ${p.id}`"><SwitchSquarePort kind="optical" :label="p.label" /></span>
              <span v-for="p in ports(slot, 'usb', slot.usb_count)" :key="p.id" class="usb" :title="`${p.label} · ${p.id}`">USB</span>
            </span>
          </button>
        </section>
        <aside class="service-module">
          <span class="service-mark">{{ profile.shortLabel }}</span>
          <b>{{ profile.deploymentMode }}</b>
          <small>MGMT</small><i class="service-port" />
          <small>CONSOLE</small><i class="console-port" />
          <span class="ground" title="接地端子" />
        </aside>
      </div>
      <footer class="rear-footer"><span>冗余电源 ×{{ psus }}</span><span>风扇模组 ×{{ fans }}</span><span>接口 ID 唯一可定位</span></footer>
    </div>
    <div class="rack-ear"><i /><i /><i /></div>
  </div>
</template>

<style scoped>
*{box-sizing:border-box}.security-rear{width:100%;max-width:860px;height:auto;display:flex;overflow:hidden;border:1px solid #27323b;border-radius:3px;background:linear-gradient(180deg,#8b959d,#38444d 18%,#202a32 82%,#69747c);box-shadow:inset 0 0 0 1px rgba(255,255,255,.26),0 8px 20px rgba(0,0,0,.22)}
.rack-ear{width:13px;flex:0 0 13px;display:flex;flex-direction:column;justify-content:space-around;align-items:center;background:linear-gradient(90deg,#242d34,#6d7881 48%,#202830);border-right:1px solid #11181d}.rack-ear:last-child{border-right:0;border-left:1px solid #11181d}.rack-ear i{width:5px;height:5px;border-radius:50%;background:#090d10;box-shadow:0 0 0 1px #b2bbc1}
.rear-shell{flex:1;min-width:0;display:flex;flex-direction:column;background:linear-gradient(180deg,#343e46,#171e24)}.rear-header{height:18px;display:flex;align-items:center;gap:7px;padding:0 8px;color:#dce6ec;border-bottom:1px solid #0b1014;font:700 7px Arial;letter-spacing:.07em}.rear-header b{margin-right:auto;color:var(--security-accent)}.rear-header span{color:#8f9da7}.status-led{width:5px;height:5px;border-radius:50%;background:#58d269;box-shadow:0 0 4px #58d269}
.rear-content{flex:1;min-height:0;display:grid;grid-template-columns:minmax(88px,16%) minmax(72px,15%) minmax(0,1fr) minmax(78px,12%);gap:7px;padding:6px 8px}.psu-bank,.fan-bank{min-width:0;min-height:0;display:flex;flex-direction:column;justify-content:center;gap:7px}.psu-module{position:relative;flex:0 1 58px;min-height:28px;display:grid;grid-template-columns:minmax(22px,1fr) minmax(18px,.65fr);grid-template-rows:1fr 8px;gap:3px;padding:4px;color:#c4ced4;border:1px solid #11181d;background:linear-gradient(145deg,#77828a,#303a42 72%);box-shadow:inset 0 0 0 1px rgba(255,255,255,.2)}.psu-fan{grid-row:1/3;display:flex;align-items:center;justify-content:center;border:1px solid #1b2227;background:repeating-radial-gradient(circle,#12171b 0 1px,#647078 2px 4px)}.psu-fan i{width:72%;aspect-ratio:1;border-radius:50%;background:conic-gradient(#151b1f 0 17%,transparent 18% 24%,#151b1f 25% 42%,transparent 43% 49%,#151b1f 50% 67%,transparent 68% 74%,#151b1f 75% 92%,transparent 93%)}.iec-inlet{display:grid;grid-template-columns:repeat(3,1fr);align-items:center;gap:2px;padding:3px;border:2px solid #11171b;border-radius:2px 2px 5px 5px;background:#080b0d}.iec-inlet i{height:3px;background:#6f767b}.psu-led{width:4px;height:4px;justify-self:end;border-radius:50%;background:#57d469;box-shadow:0 0 4px #57d469}.psu-module>b{position:absolute;right:3px;bottom:2px;font:700 5px Arial}
.fan-bank{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));grid-auto-rows:minmax(18px,1fr);gap:4px}.fan-module{position:relative;min-width:0;min-height:0;display:flex;align-items:center;justify-content:center;border:1px solid #202a31;background:linear-gradient(145deg,#7a858c,#3a454d);box-shadow:inset 0 0 0 2px rgba(255,255,255,.13)}.fan-rotor{width:min(76%,54px);aspect-ratio:1;border-radius:50%;background:conic-gradient(#161c20 0 11%,#768189 12% 23%,#161c20 24% 36%,#768189 37% 48%,#161c20 49% 61%,#768189 62% 73%,#161c20 74% 86%,#768189 87%);box-shadow:0 0 0 2px #20282e,inset 0 0 0 4px #4d5860}.fan-rotor i{position:absolute}.fan-module>b{position:absolute;left:2px;bottom:1px;color:#d3dade;font:700 5px Arial}
.rear-io-bank{min-width:0;min-height:0;display:flex;align-items:stretch;gap:4px;padding:3px;border:1px solid #131a1f;background:#59636b;overflow:hidden}.rear-slot{flex:1 1 0;min-width:0;position:relative;display:flex;flex-direction:column;gap:3px;padding:10px 3px 3px;overflow:hidden;color:#cad3d9;border:1px solid #182127;border-top:2px solid var(--security-accent);background:linear-gradient(180deg,#7f8990,#303a41);cursor:pointer}.rear-slot:hover{box-shadow:inset 0 0 0 1px var(--security-accent)}.rear-slot-title{position:absolute;left:4px;top:2px;font:700 6px Arial}.rear-slot-ports{display:flex;flex-wrap:wrap;align-content:flex-end;gap:2px;margin-top:auto}.port{width:16px;height:16px;display:inline-flex}.usb{padding:2px;color:#ddd;background:#171a1c;border:1px solid #8c9398;font:700 5px Arial}
.service-module{min-width:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;padding:4px;color:#b7c2c9;border:1px solid #151d22;background:linear-gradient(145deg,#66727a,#2c373e);font:700 5px Arial}.service-mark{width:100%;padding:2px;text-align:center;color:#fff;background:var(--security-accent)}.service-module>b{max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:5px}.service-module small{font-size:4px}.service-port{width:20px;height:17px;border:2px solid #172027;background:#080b0d}.console-port{width:22px;height:8px;border:1px solid #141a1e;background:#20262a;box-shadow:inset 0 0 0 2px #080a0b}.ground{width:11px;height:11px;border-radius:50%;background:radial-gradient(circle,#20272c 0 25%,#c0c7cb 27% 51%,#3a444b 53%)}
.rear-footer{height:14px;display:flex;justify-content:space-between;align-items:center;padding:0 8px;color:#83919b;border-top:1px solid #303b43;font:600 6px Arial}
.u1 .rear-header{height:13px;font-size:6px}.u1 .rear-content{grid-template-columns:minmax(76px,15%) minmax(58px,13%) minmax(0,1fr) minmax(66px,11%);gap:4px;padding:3px 5px}.u1 .psu-bank{flex-direction:row;gap:3px}.u1 .psu-module{height:100%;min-height:0;padding:2px;grid-template-columns:1fr 10px}.u1 .fan-bank{grid-template-columns:repeat(4,minmax(0,1fr));gap:2px}.u1 .port{width:12px;height:12px}.u1 .rear-slot{padding-top:8px}.u1 .service-module{gap:1px;padding:2px}.u1 .rear-footer{height:10px;font-size:5px}
[data-panel-mode="isolation"] .rear-io-bank{background:linear-gradient(90deg,#3a5f84 0 49.4%,#d5dce0 49.5% 50.5%,#75453f 50.6%)}[data-panel-mode="collector"] .rear-slot{background:linear-gradient(180deg,#6e817b,#283b35)}[data-panel-mode="sensor"] .rear-slot{border-top-color:#c99a3d}[data-panel-mode="cleaner"] .psu-module{box-shadow:inset 0 0 0 1px rgba(212,93,121,.38)}[data-panel-mode="crypto"] .service-module{background:linear-gradient(145deg,#695c78,#2a2431)}
</style>