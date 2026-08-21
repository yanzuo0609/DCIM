<script setup lang="ts">
import { computed } from 'vue'
import type { DeviceType, ParamDiskSpec, ParamProfile } from '@/api/device'
import {
  RESOURCE_CLASS_LABELS,
  displayDeviceTypeName,
  isDeviceTypeCode,
  resolveDeviceTypeCode,
  resourceClassOf,
} from '@/utils/deviceTypeCatalog'

const props = defineProps<{
  modelValue: boolean
  profile: ParamProfile | null
  deviceTypes?: DeviceType[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

type FieldItem = { label: string; value: string }

const p = computed(() => props.profile?.payload || null)

/** 仅当用户真正填写/选择了内容时才视为有值 */
function filledText(v: unknown): string | null {
  if (v === null || v === undefined) return null
  if (typeof v === 'number') {
    if (Number.isNaN(v)) return null
    return String(v)
  }
  if (typeof v === 'boolean') return v ? '是' : '否'
  const text = String(v).trim()
  if (!text) return null
  if (text === '—' || text === '-' || text === 'null' || text === 'undefined') return null
  return text
}

function push(
  fields: FieldItem[],
  label: string,
  value: unknown,
  opts?: { suffix?: string },
) {
  const text = filledText(value)
  if (text == null) return
  fields.push({
    label,
    value: opts?.suffix ? `${text}${opts.suffix}` : text,
  })
}

function diskLabel(role: string) {
  if (role === 'system') return '系统盘'
  if (role === 'cache') return '缓存盘'
  if (role === 'data') return '数据盘'
  return '磁盘'
}

function diskText(d: ParamDiskSpec) {
  const bits: string[] = []
  if (d.count != null && d.size_gb != null) bits.push(`${d.count}×${d.size_gb}GB`)
  else if (d.size_gb != null) bits.push(`${d.size_gb}GB`)
  else if (d.count != null) bits.push(`${d.count}块`)
  if (filledText(d.interface)) bits.push(String(d.interface).trim())
  if (filledText(d.media_type)) bits.push(String(d.media_type).toUpperCase())
  return bits.join(' ')
}

function typeNameText() {
  const id = props.profile?.device_type_id || props.profile?.payload?.device_type_id
  if (!filledText(id)) return null
  const name = displayDeviceTypeName(props.deviceTypes || [], id)
  return filledText(name)
}

function typeClassText() {
  const id = props.profile?.device_type_id || props.profile?.payload?.device_type_id
  if (!filledText(id)) return null
  const code = resolveDeviceTypeCode(props.deviceTypes || [], id)
  if (!isDeviceTypeCode(code)) return null
  return filledText(RESOURCE_CLASS_LABELS[resourceClassOf(code)])
}

const basicFields = computed((): FieldItem[] => {
  const row = props.profile
  if (!row) return []
  const fields: FieldItem[] = []
  push(fields, '设备参数ID', row.code)
  push(fields, '设备名称', row.name)
  push(fields, '产品型号', row.source_device_model || p.value?.source_device_model)
  push(fields, '产品厂商', row.source_manufacturer || p.value?.source_manufacturer)
  const typeName = typeNameText()
  if (typeName) {
    fields.push({ label: '设备类型', value: typeName })
    const typeClass = typeClassText()
    if (typeClass) fields.push({ label: '类型归类', value: typeClass })
  }
  return fields
})

const configFields = computed((): FieldItem[] => {
  const payload = p.value
  if (!payload) return []
  const fields: FieldItem[] = []
  push(fields, '电源功率', payload.psu_power_w, { suffix: 'W' })
  push(fields, '设备高度', payload.height_u, { suffix: 'U' })
  push(fields, 'CPU型号', payload.cpu?.model)
  push(fields, 'CPU颗数', payload.cpu?.count)
  push(fields, 'CPU核心数', payload.cpu?.cores)
  push(fields, 'CPU架构', payload.cpu?.architecture)
  push(fields, '内存型号', payload.memory?.ddr_type)
  push(fields, '单条内存', payload.memory?.stick_size_gb, { suffix: 'GB' })
  push(fields, '总内存', payload.memory?.size_gb, { suffix: 'GB' })
  push(fields, '内存条数', payload.memory?.modules)

  const disks = payload.disks || []
  for (const role of ['system', 'cache', 'data'] as const) {
    const items = disks.filter((d) => d.role === role).map(diskText).filter((t) => !!t)
    if (items.length) fields.push({ label: diskLabel(role), value: items.join('；') })
  }
  const legacy = disks.filter((d) => !d.role).map(diskText).filter(Boolean)
  if (legacy.length) fields.push({ label: '磁盘', value: legacy.join('；') })

  push(fields, '千兆网卡数量', payload.nic?.ge_nic_count)
  push(fields, '千兆接口数量', payload.nic?.ge_port_count)
  push(fields, '万兆网卡数量', payload.nic?.xe_nic_count)
  push(fields, '万兆接口数量', payload.nic?.xe_port_count)
  push(fields, '板载接口类型', payload.nic?.onboard_type)
  push(fields, '板载接口数量', payload.nic?.onboard_count)
  push(fields, 'PCIe插槽数量', payload.nic?.pcie_slot_count)
  push(fields, 'RAID卡型号', payload.raid?.model)
  push(fields, 'RAID参数', payload.raid?.params)
  push(fields, '显卡型号', payload.gpu?.model)
  push(fields, '显卡个数', payload.gpu?.count)
  push(fields, '显存大小', payload.gpu?.vram_gb, { suffix: 'GB' })
  push(fields, '显存带宽', payload.gpu?.bandwidth)
  return fields
})

const networkFields = computed((): FieldItem[] => {
  const sw = p.value?.switch
  if (!sw) return []
  const fields: FieldItem[] = []
  push(fields, '交换容量', sw.switching_capacity)
  push(fields, '包转发率', sw.forwarding_rate)
  push(fields, '业务板卡数量', sw.service_card_count)
  push(fields, '交换板卡数量', sw.fabric_card_count)
  push(fields, '接口卡数量', sw.interface_card_count)
  push(fields, '接口卡类型', sw.interface_card_type)
  push(fields, 'DOWNLINK接口个数', sw.downlink_port_count)
  push(fields, 'UPLINK上联接口类型', sw.uplink_port_type)
  push(fields, 'UPLINK上联接口个数', sw.uplink_port_count)
  return fields
})

const otherFields = computed((): FieldItem[] => {
  const fields: FieldItem[] = []
  push(fields, '手动说明', p.value?.other_params || props.profile?.other_params)
  push(fields, '详细参数', p.value?.detail_params)
  return fields
})

const sections = computed(() =>
  [
    { title: '基本信息', fields: basicFields.value },
    { title: '参数配置', fields: configFields.value },
    { title: '网络参数', fields: networkFields.value },
    { title: '其他参数', fields: otherFields.value },
  ].filter((s) => s.fields.length > 0),
)

const hasAnyDetail = computed(() => sections.value.length > 0)
</script>

<template>
  <el-dialog
    v-model="visible"
    title="参数详细"
    width="640px"
    destroy-on-close
    top="6vh"
    class="param-detail-dialog"
  >
    <template v-if="profile && hasAnyDetail">
      <div class="detail-sheet">
        <section v-for="sec in sections" :key="sec.title" class="block">
          <h4 class="sec-title">{{ sec.title }}</h4>
          <dl class="field-list">
            <div v-for="(f, idx) in sec.fields" :key="`${sec.title}-${f.label}-${idx}`" class="field">
              <dt>{{ f.label }}</dt>
              <dd>{{ f.value }}</dd>
            </div>
          </dl>
        </section>
      </div>
    </template>
    <el-empty v-else-if="profile" description="暂无已填写的参数" />
    <el-empty v-else description="暂无参数详情" />
    <template #footer>
      <el-button type="primary" @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.detail-sheet {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 68vh;
  overflow: auto;
  padding: 4px 2px;
}
.block {
  border: 1px solid #c5d0d8;
  border-radius: 6px;
  background: #f7f9fc;
  overflow: hidden;
}
.sec-title {
  margin: 0;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 700;
  color: #1f2a37;
  background: #e8eef5;
  border-bottom: 1px solid #c5d0d8;
}
.field-list {
  margin: 0;
  padding: 4px 0;
}
.field {
  display: grid;
  grid-template-columns: 148px 1fr;
  gap: 8px 12px;
  padding: 7px 14px;
  align-items: start;
}
.field + .field {
  border-top: 1px dashed #dde3ea;
}
.field dt {
  margin: 0;
  font-size: 12px;
  color: #64748b;
  text-align: right;
  line-height: 1.5;
}
.field dd {
  margin: 0;
  font-size: 13px;
  color: #1f2a37;
  line-height: 1.5;
  word-break: break-word;
  white-space: pre-wrap;
}
@media (max-width: 560px) {
  .field {
    grid-template-columns: 1fr;
    gap: 2px;
  }
  .field dt {
    text-align: left;
  }
}
</style>
