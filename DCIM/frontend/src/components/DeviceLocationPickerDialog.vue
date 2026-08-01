<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import RackCabinet from '@/components/RackCabinet.vue'
import { getDevice, mountDevice, unmountDevice } from '@/api/device'
import { listRooms, type Room } from '@/api/room'
import {
  getRackLayout,
  listRacks,
  type Rack,
  type RackLayoutSlot,
} from '@/api/rack'

const props = defineProps<{
  modelValue: boolean
  deviceId: string | null
  deviceName?: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const loading = ref(false)
const saving = ref(false)
const rooms = ref<Room[]>([])
const racks = ref<Rack[]>([])
const layoutSlots = ref<RackLayoutSlot[]>([])
const layoutTotalPower = ref(0)
const layoutLoading = ref(false)
const metaError = ref('')
const hydrating = ref(false)

const form = reactive({
  room_id: '' as string,
  rack_id: '' as string,
  u_position: 1 as number,
})

const filteredRacks = computed(() => {
  if (!form.room_id) return []
  return racks.value.filter((r) => r.room_id === form.room_id)
})

const selectedRack = computed(() => racks.value.find((r) => r.id === form.rack_id) || null)

async function loadAllPages<T>(
  fetcher: (page: number, pageSize: number) => Promise<{ items?: T[]; pagination?: { pages?: number } }>,
  pageSize = 500,
): Promise<T[]> {
  const first = await fetcher(1, pageSize)
  const items = [...(first.items || [])]
  const pages = Math.max(1, Number(first.pagination?.pages || 1))
  for (let page = 2; page <= pages; page += 1) {
    const data = await fetcher(page, pageSize)
    items.push(...(data.items || []))
  }
  return items
}

async function loadRooms() {
  rooms.value = await loadAllPages((page, page_size) => listRooms({ page, page_size }))
}

async function loadRacks(roomId?: string) {
  const params: Record<string, unknown> = {}
  if (roomId) params.room_id = roomId
  racks.value = await loadAllPages((page, page_size) =>
    listRacks({ ...params, page, page_size, sort: 'code', order: 'asc' }),
  )
}

async function loadDeviceIntoForm() {
  if (!props.deviceId) return
  loading.value = true
  metaError.value = ''
  hydrating.value = true
  try {
    await loadRooms()
    const device = await getDevice(props.deviceId)
    form.room_id = device.room_id || ''
    form.rack_id = device.rack_id || ''
    form.u_position = device.u_position || 1
    if (form.room_id) {
      await loadRacks(form.room_id)
    } else {
      racks.value = []
    }
    if (form.rack_id) await loadLayout(form.rack_id)
    if (!rooms.value.length) {
      metaError.value = '未读取到机房列表，请确认已创建机房，且当前账号有查看权限'
    }
  } catch (err: unknown) {
    const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
    metaError.value = msg || '加载机房/机柜失败'
    ElMessage.error(metaError.value)
  } finally {
    loading.value = false
    hydrating.value = false
  }
}

async function loadLayout(rackId: string) {
  layoutLoading.value = true
  try {
    const data = await getRackLayout(rackId)
    layoutSlots.value = data.slots || []
    layoutTotalPower.value = data.total_power || 0
    if (data.rack && !racks.value.find((r) => r.id === data.rack.id)) {
      racks.value.push(data.rack)
    }
  } catch {
    layoutSlots.value = []
    layoutTotalPower.value = 0
  } finally {
    layoutLoading.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) void loadDeviceIntoForm()
  },
)

watch(
  () => form.room_id,
  async (roomId, prev) => {
    if (!props.modelValue || hydrating.value || roomId === prev) return
    form.rack_id = ''
    layoutSlots.value = []
    layoutTotalPower.value = 0
    if (!roomId) {
      racks.value = []
      return
    }
    try {
      await loadRacks(roomId)
      if (!filteredRacks.value.length) {
        ElMessage.warning('该机房下暂无机柜，请先在机房/机柜管理中创建')
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      ElMessage.error(msg || '加载机柜列表失败')
      racks.value = []
    }
  },
)

watch(
  () => form.rack_id,
  (rackId) => {
    if (rackId) void loadLayout(rackId)
    else {
      layoutSlots.value = []
      layoutTotalPower.value = 0
    }
  },
)

async function onConfirm() {
  if (!props.deviceId) return
  if (!form.room_id) {
    ElMessage.warning('请选择机房')
    return
  }
  if (!form.rack_id) {
    ElMessage.warning('请选择机柜')
    return
  }
  if (!form.u_position || form.u_position < 1) {
    ElMessage.warning('请选择 U 位')
    return
  }
  saving.value = true
  try {
    await mountDevice(form.rack_id, props.deviceId, form.u_position)
    ElMessage.success('位置已更新，机柜布局已同步')
    visible.value = false
    emit('saved')
  } catch {
    ElMessage.error('上架失败，U 位冲突或参数错误')
  } finally {
    saving.value = false
  }
}

async function onUnmount() {
  if (!props.deviceId) return
  saving.value = true
  try {
    await unmountDevice(props.deviceId)
    ElMessage.success('已下架')
    visible.value = false
    emit('saved')
  } catch {
    ElMessage.error('下架失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="`编辑设备位置${deviceName ? ` · ${deviceName}` : ''}`"
    width="900px"
    destroy-on-close
    append-to-body
  >
    <div v-loading="loading" class="mount-layout">
      <el-form label-width="72px" class="mount-form">
        <el-alert
          v-if="metaError"
          type="warning"
          :closable="false"
          show-icon
          :title="metaError"
          class="meta-alert"
        />
        <el-form-item label="机房" required>
          <el-select
            v-model="form.room_id"
            style="width: 100%"
            filterable
            clearable
            placeholder="选择机房"
            :disabled="!rooms.length"
          >
            <el-option
              v-for="r in rooms"
              :key="r.id"
              :label="r.datacenter_name ? `${r.name}（${r.datacenter_name}）` : r.name"
              :value="r.id"
            />
          </el-select>
          <p v-if="!loading && !rooms.length" class="hint warn">暂无机房数据</p>
        </el-form-item>
        <el-form-item label="机柜" required>
          <el-select
            v-model="form.rack_id"
            style="width: 100%"
            filterable
            clearable
            placeholder="请先选择机房"
            :disabled="!form.room_id"
          >
            <el-option
              v-for="r in filteredRacks"
              :key="r.id"
              :label="`${r.code} · 空闲 ${r.free_u}U`"
              :value="r.id"
            />
          </el-select>
          <p v-if="form.room_id && !filteredRacks.length" class="hint warn">该机房下暂无机柜</p>
        </el-form-item>
        <el-form-item label="U 位" required>
          <el-input-number
            v-model="form.u_position"
            :min="1"
            :max="selectedRack?.total_u || 60"
          />
        </el-form-item>
        <p v-if="selectedRack" class="hint">
          {{ selectedRack.code }} · {{ selectedRack.total_u }}U · 利用率 {{ selectedRack.utilization }}%
        </p>
        <p class="hint">确认后将写入机房机柜布局图，与设备管理上架位置保持一致。</p>
      </el-form>
      <div v-loading="layoutLoading" class="mount-preview">
        <RackCabinet
          v-if="form.rack_id"
          selectable
          compact
          :code="selectedRack?.code || '机柜'"
          :total-u="selectedRack?.total_u || 42"
          :slots="layoutSlots"
          :total-power="layoutTotalPower"
          :visual-style="(selectedRack?.visual_style as any) || 'classic'"
          :selected-u="form.u_position"
          :highlight-device-id="deviceId || undefined"
          @select-u="(u) => { form.u_position = u }"
        />
        <el-empty v-else description="请选择机柜查看布局" :image-size="64" />
        <p v-if="form.rack_id" class="hint">点击空闲 U 位快速选择</p>
      </div>
    </div>
    <template #footer>
      <el-button :disabled="!deviceId || saving" @click="onUnmount">下架</el-button>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="onConfirm">确认上架/改位</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.mount-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 16px;
  min-height: 420px;
}

.mount-form {
  min-width: 0;
}

.meta-alert {
  margin-bottom: 12px;
}

.mount-preview {
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  max-height: 560px;
  overflow: auto;
}

.hint {
  margin: 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}

.hint.warn {
  color: #e6a23c;
  margin-top: 4px;
}

@media (max-width: 900px) {
  .mount-layout {
    grid-template-columns: 1fr;
  }
}
</style>
