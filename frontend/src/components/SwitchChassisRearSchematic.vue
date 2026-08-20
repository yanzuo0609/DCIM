<script setup lang="ts">
import { computed } from 'vue'
import { CHASSIS_DEMO, rackPanelAspect } from '@/utils/switchModelAttrs'

const props = defineProps<{
  heightU: number
  expansionSlots?: number
  fanCount: number
  psuCount: number
}>()

const fans = computed(() => Math.max(0, Math.min(16, Math.trunc(props.fanCount) || 0)))
const psus = computed(() => Math.max(0, Math.min(16, Math.trunc(props.psuCount) || 0)))
const psuLeft = computed(() => Math.ceil(psus.value / 2))
const psuRight = computed(() => Math.floor(psus.value / 2))
const fanCols = computed(() => (fans.value <= 1 ? 1 : 2))
const fanRows = computed(() => Math.max(1, Math.ceil(fans.value / Math.max(1, fanCols.value))))
const frameStyle = computed(() => ({
  aspectRatio: rackPanelAspect(props.heightU),
  maxWidth: `${CHASSIS_DEMO.maxW}px`,
}))

const fanGridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${Math.max(1, fanCols.value)}, minmax(0, 1fr))`,
  gridTemplateRows: `repeat(${fanRows.value}, minmax(0, 1fr))`,
}))
</script>

<template>
  <div
    class="rear"
    :style="frameStyle"
    :title="`${heightU}U · 风扇 ${fans} · 电源 ${psus}`"
  >
    <span class="rack-ear ear-left"><i /><i /><i /></span>
    <span class="rack-ear ear-right"><i /><i /><i /></span>
    <div class="rear-inner">
      <div class="rear-head">
        <b>MODULAR CORE · REAR</b>
        <span>{{ heightU }}U</span>
        <i class="ok" />
      </div>
      <div class="rear-main">
        <div class="psu-col">
          <span v-for="i in psuLeft" :key="`l${i}`" class="psu" :title="`电源 ${i}`">
            <i class="psu-fan" /><i class="psu-inlet" /><i class="psu-led" /><b>PSU {{ i }}</b>
          </span>
        </div>
        <div class="fan-grid" :style="fanGridStyle">
          <span v-for="i in fans" :key="`f${i}`" class="fan" :title="`风扇 ${i}`">
            <i class="fan-ring"><i /></i><b>FAN {{ i }}</b>
          </span>
        </div>
        <div class="psu-col">
          <span v-for="i in psuRight" :key="`r${i}`" class="psu" :title="`电源 ${psuLeft + i}`">
            <i class="psu-fan" /><i class="psu-inlet" /><i class="psu-led" /><b>PSU {{ psuLeft + i }}</b>
          </span>
        </div>
      </div>
      <div class="rear-base">
        <span><b>CMU</b><i class="led ok" /><i class="led" /></span>
        <span><b>SFU</b><i class="port" /><i class="port" /></span>
        <span><b>GROUND</b><i class="ground" /></span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rear {
  box-sizing: border-box;
  width: 100%;
  position: relative;
  padding: 5px 14px;
  background: linear-gradient(145deg,#8b949c,#38434d 18%,#202a33 82%,#69747d);
  border: 2px solid #1c252d;
  border-radius: 3px;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,.25),0 5px 16px rgba(21,33,43,.22);
  overflow: hidden;
}
.rack-ear { position: absolute; top: 3px; bottom: 3px; width: 9px; display: flex; flex-direction: column; justify-content: space-around; align-items: center; background: linear-gradient(90deg,#2e3942,#77828b 50%,#252f37); border: 1px solid #111920; z-index: 2; }
.rack-ear>i { width: 4px; height: 4px; border-radius: 50%; background: #0d1216; box-shadow: 0 0 0 1px #aeb6bc; }
.ear-left { left: 2px; }.ear-right { right: 2px; transform: scaleX(-1); }
.rear-inner {
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-rows: 18px minmax(0, 1fr) 34px;
  background: #5e656e;
  border: 1px solid #2c3e50;
  box-sizing: border-box;
  overflow: hidden;
}
.rear-head { min-height: 0; display: flex; align-items: center; gap: 7px; padding: 0 8px; color: #dce7ed; background: linear-gradient(180deg,#303b44,#172129); border-bottom: 1px solid #0e151a; font: 700 7px Arial; letter-spacing: .08em; }
.rear-head b { margin-right: auto; }.rear-head span { color: #91a2ad; }.rear-head i { width: 5px; height: 5px; border-radius: 50%; }
.ok { background: #58d269!important; box-shadow: 0 0 4px #58d269; }
.rear-main {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(92px, 18%) minmax(0, 1fr) minmax(92px, 18%);
  gap: 14px;
  padding: 7px 12px;
  align-items: center;
}
.psu-col {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 10px;
  padding: 5px 0;
  overflow: hidden;
}
.psu { position: relative; display: grid; grid-template-columns: minmax(24px,1fr) minmax(18px,.62fr); grid-template-rows: 1fr 12px; gap: 4px; flex: 0 1 66px; width: min(100%,118px); min-height: 38px; max-height: 66px; padding: 5px; color: #aeb9c0; background: linear-gradient(145deg,#7c878f,#303a42 70%); border: 1px solid #11181d; border-radius:2px; box-shadow: inset 0 0 0 1px rgba(255,255,255,.22),0 2px 3px rgba(0,0,0,.24); box-sizing: border-box; }
.psu-fan { grid-row: 1/3; border-radius: 50%; border: 2px solid #20282e; background: repeating-radial-gradient(circle,#171c20 0 2px,#68747c 3px 5px); box-shadow: inset 0 0 0 2px #8a959c; }
.psu-inlet { position:relative; border: 2px solid #11171b; border-radius: 2px 2px 6px 6px; background:linear-gradient(180deg,#171c20,#070a0c); box-shadow:inset 0 0 0 1px #5f686e; }
.psu-led { width: 5px; height: 5px; align-self: center; justify-self: end; border-radius: 50%; background: #5ed66d; box-shadow: 0 0 4px #5ed66d; }
.psu b { position: absolute; right: 3px; bottom: 2px; font: 700 6px Arial; }
.fan-grid {
  min-width: 0;
  min-height: 0;
  height: 100%;
  display: grid;
  gap: 4px;
  overflow: hidden;
}
.fan { position: relative; display: flex; align-items: center; justify-content: center; min-width: 0; min-height: 0; box-sizing: border-box; border: 1px solid #202b32; background: linear-gradient(145deg,#7b858c,#404b53); box-shadow: inset 0 0 0 2px rgba(232,236,242,.22); overflow: hidden; }
.fan-ring { width: min(70%,90px); aspect-ratio: 1; display: flex; align-items: center; justify-content: center; border-radius: 50%; border: 3px solid #20282e; background: conic-gradient(#1b2227 0 10%,#758087 11% 22%,#1b2227 23% 35%,#758087 36% 47%,#1b2227 48% 60%,#758087 61% 72%,#1b2227 73% 85%,#758087 86% 97%,#1b2227 98%); box-shadow: 0 0 0 2px #9aa3a8,inset 0 0 0 5px #313b42; }
.fan-ring>i { width: 18%; aspect-ratio: 1; border-radius: 50%; background: #11171b; box-shadow: 0 0 0 2px #8d989f; }
.fan>b { position: absolute; left: 3px; bottom: 2px; color: #d2d9dd; font: 700 6px Arial; }
.rear-base { min-height: 0; display: grid; grid-template-columns: 1fr 1fr .7fr; gap: 5px; margin: 0 10px 6px; padding: 3px; background: #202a31; border: 1px solid #11191e; box-sizing: border-box; }
.rear-base>span { display: flex; align-items: center; gap: 4px; padding: 2px 5px; color: #c6d0d6; background: linear-gradient(180deg,#59656d,#313c43); border: 1px solid #182127; font: 700 6px Arial; }
.rear-base b { margin-right: auto; }.led { width: 5px; height: 5px; border-radius: 50%; background: #707a81; }.port { width: 16px; height: 8px; background: #12181c; border: 1px solid #05090b; }.ground { width: 10px; height: 10px; border-radius: 50%; background: radial-gradient(circle,#252d32 0 25%,#b9c0c4 27% 50%,#384148 52%); }
</style>
