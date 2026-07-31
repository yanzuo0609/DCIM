<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createParamProfile,
  deleteParamProfile,
  listParamProfiles,
  updateParamProfile,
  type ParamCustomField,
  type ParamDiskSpec,
  type ParamProfile,
  type ParamProfilePayload,
} from '@/api/device'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const canUpdate = auth.hasPermission('device:update')
const canCreate = auth.hasPermission('device:create')
const canDelete = auth.hasPermission('device:delete') || canUpdate

const loading = ref(false)
const profiles = ref<ParamProfile[]>([])
const dialogVisible = ref(false)
const editingId = ref<string | null>(null)
const osInput = ref('')

const DDR_OPTIONS = ['DDR3', 'DDR4', 'DDR5', 'LPDDR4', 'LPDDR5']
const DISK_INTERFACE_OPTIONS = ['SATA', 'SAS', 'NVMe', 'PCIe', 'M.2', 'U.2']
const DISK_MEDIA_OPTIONS = [
  { value: 'ssd', label: 'SSD' },
  { value: 'hdd', label: '机械盘' },
  { value: 'nvme', label: 'NVMe' },
]
const DEFAULT_DISK_SPEC_COUNT = 3
const MAX_DISK_SPEC_COUNT = 20

const form = reactive({
  code: '',
  name: '',
  description: '',
  cpu_cores: null as number | null,
  cpu_architecture: null as 'c86' | 'arm' | null,
  cpu_model: '',
  memory_size_gb: null as number | null,
  memory_ddr_type: '' as string,
  memory_modules: null as number | null,
  disks: [] as ParamDiskSpec[],
  fan_count: null as number | null,
  fan_model: '',
  psu_power_w: null as number | null,
  raid_model: '',
  raid_params: '',
  supported_os: [] as string[],
  custom: [] as ParamCustomField[],
})

function emptyDisk(): ParamDiskSpec {
  return { size_gb: null, count: null, interface: null, media_type: null }
}

function defaultDiskRows(count = DEFAULT_DISK_SPEC_COUNT): ParamDiskSpec[] {
  return Array.from({ length: count }, () => emptyDisk())
}

function isDiskRowFilled(d: ParamDiskSpec): boolean {
  return d.size_gb != null || d.count != null || !!d.interface || !!d.media_type
}

function resetForm() {
  form.code = ''
  form.name = ''
  form.description = ''
  form.cpu_cores = null
  form.cpu_architecture = null
  form.cpu_model = ''
  form.memory_size_gb = null
  form.memory_ddr_type = 'DDR5'
  form.memory_modules = null
  form.disks = defaultDiskRows()
  form.fan_count = null
  form.fan_model = ''
  form.psu_power_w = null
  form.raid_model = ''
  form.raid_params = ''
  form.supported_os = []
  form.custom = []
  osInput.value = ''
}

function fillForm(row: ParamProfile) {
  const p = row.payload || {}
  form.code = row.code
  form.name = row.name
  form.description = row.description || ''
  form.cpu_cores = p.cpu?.cores ?? null
  form.cpu_architecture = p.cpu?.architecture ?? null
  form.cpu_model = p.cpu?.model || ''
  form.memory_size_gb = p.memory?.size_gb ?? null
  form.memory_ddr_type = p.memory?.ddr_type || 'DDR5'
  form.memory_modules = p.memory?.modules ?? null
  form.disks = p.disks?.length
    ? p.disks.map((d) => ({
        size_gb: d.size_gb ?? null,
        count: d.count ?? null,
        interface: d.interface || null,
        media_type: d.media_type || null,
      }))
    : defaultDiskRows()
  form.fan_count = p.fan_count ?? null
  form.fan_model = p.fan_model || ''
  form.psu_power_w = p.psu_power_w ?? null
  form.raid_model = p.raid?.model || ''
  form.raid_params = p.raid?.params || ''
  form.supported_os = [...(p.supported_os || [])]
  form.custom = (p.custom || []).map((c) => ({ key: c.key, value: c.value }))
  osInput.value = ''
}

function buildPayload(): ParamProfilePayload {
  return {
    cpu: {
      cores: form.cpu_cores,
      architecture: form.cpu_architecture,
      model: form.cpu_model || null,
    },
    memory: {
      size_gb: form.memory_size_gb,
      ddr_type: form.memory_ddr_type || null,
      modules: form.memory_modules,
    },
    disks: form.disks.filter(isDiskRowFilled).map((d) => ({
      size_gb: d.size_gb,
      count: d.count,
      interface: d.interface || null,
      media_type: d.media_type || null,
    })),
    fan_count: form.fan_count,
    fan_model: form.fan_model || null,
    psu_power_w: form.psu_power_w,
    raid: {
      model: form.raid_model || null,
      params: form.raid_params || null,
    },
    supported_os: [...form.supported_os],
    custom: form.custom.filter((c) => c.key.trim()),
  }
}

function addDiskRow() {
  if (form.disks.length >= MAX_DISK_SPEC_COUNT) {
    ElMessage.warning(`最多添加 ${MAX_DISK_SPEC_COUNT} 种磁盘规格`)
    return
  }
  form.disks.push(emptyDisk())
}

function removeDiskRow(idx: number) {
  if (form.disks.length <= 1) {
    form.disks[0] = emptyDisk()
    return
  }
  form.disks.splice(idx, 1)
}

function addOsTag() {
  const v = osInput.value.trim()
  if (!v) return
  if (!form.supported_os.includes(v)) form.supported_os.push(v)
  osInput.value = ''
}

function removeOsTag(os: string) {
  form.supported_os = form.supported_os.filter((x) => x !== os)
}

function addCustomRow() {
  form.custom.push({ key: '', value: '' })
}

function removeCustomRow(idx: number) {
  form.custom.splice(idx, 1)
}

async function loadData() {
  loading.value = true
  try {
    profiles.value = await listParamProfiles()
  } catch {
    profiles.value = []
    ElMessage.error('加载设备参数失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: ParamProfile) {
  editingId.value = row.id
  fillForm(row)
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.code || !form.name) {
    ElMessage.warning('请填写编码与名称')
    return
  }
  const payload = buildPayload()
  if (editingId.value) {
    await updateParamProfile(editingId.value, {
      name: form.name,
      payload,
      description: form.description || null,
    })
  } else {
    await createParamProfile({
      code: form.code,
      name: form.name,
      payload,
      description: form.description || null,
    })
  }
  ElMessage.success('设备参数已保存')
  dialogVisible.value = false
  await loadData()
}

async function handleDelete(row: ParamProfile) {
  await ElMessageBox.confirm(`确定删除设备参数「${row.name}」吗？`, '确认删除', { type: 'warning' })
  await deleteParamProfile(row.id)
  ElMessage.success('已删除')
  await loadData()
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <div class="param-panel">
    <div class="toolbar">
      <el-button size="small" :loading="loading" @click="loadData">刷新</el-button>
      <el-button v-if="canCreate || canUpdate" type="primary" size="small" @click="openCreate">
        新建设备参数
      </el-button>
    </div>

    <el-table v-loading="loading" :data="profiles" stripe size="small" max-height="520">
      <el-table-column prop="code" label="编码" width="130" show-overflow-tooltip />
      <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip />
      <el-table-column label="配置摘要" min-width="260" show-overflow-tooltip>
        <template #default="{ row }">{{ row.summary || '—' }}</template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">{{ row.description || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="130" fixed="right">
        <template #default="{ row }">
          <el-button v-if="canUpdate" type="primary" link @click="openEdit(row)">编辑</el-button>
          <el-button v-if="canDelete" type="danger" link @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑设备参数' : '新建设备参数'"
      width="760px"
      destroy-on-close
      top="4vh"
    >
      <el-form label-width="100px" class="param-form" size="small">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="编码" required>
              <el-input v-model="form.code" :disabled="!!editingId" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名称" required>
              <el-input v-model="form.name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>

        <div class="param-section-title">CPU</div>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="核心数">
              <el-input-number v-model="form.cpu_cores" :min="1" :max="1024" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="架构">
              <el-select v-model="form.cpu_architecture" clearable style="width: 100%" placeholder="选择架构">
                <el-option label="C86" value="c86" />
                <el-option label="ARM" value="arm" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="型号">
              <el-input v-model="form.cpu_model" placeholder="可选" />
            </el-form-item>
          </el-col>
        </el-row>

        <div class="param-section-title">内存</div>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="大小(GB)">
              <el-input-number v-model="form.memory_size_gb" :min="0" :step="8" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="DDR 类型">
              <el-select v-model="form.memory_ddr_type" allow-create filterable style="width: 100%">
                <el-option v-for="d in DDR_OPTIONS" :key="d" :label="d" :value="d" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="条数">
              <el-input-number v-model="form.memory_modules" :min="0" :max="128" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <div class="param-section-title">
          <span>磁盘规格（默认 {{ DEFAULT_DISK_SPEC_COUNT }} 种）</span>
          <el-button
            type="primary"
            link
            :disabled="form.disks.length >= MAX_DISK_SPEC_COUNT"
            @click="addDiskRow"
          >
            + 添加磁盘规格
          </el-button>
        </div>
        <p class="disk-hint">
          每种规格填写：单盘容量、块数、接口与盘类型。当前
          {{ form.disks.length }} / {{ MAX_DISK_SPEC_COUNT }}
        </p>
        <div v-for="(disk, idx) in form.disks" :key="idx" class="disk-row">
          <el-form-item :label="`规格 ${idx + 1}`" label-width="70px">
            <div class="disk-fields">
              <el-input-number
                v-model="disk.size_gb"
                :min="0"
                :step="100"
                placeholder="单盘GB"
                controls-position="right"
              />
              <span class="disk-field-label">GB ×</span>
              <el-input-number
                v-model="disk.count"
                :min="0"
                :max="100"
                placeholder="块数"
                controls-position="right"
              />
              <span class="disk-field-label">块</span>
              <el-select
                v-model="disk.interface"
                clearable
                allow-create
                filterable
                placeholder="接口"
                style="width: 110px"
              >
                <el-option v-for="i in DISK_INTERFACE_OPTIONS" :key="i" :label="i" :value="i" />
              </el-select>
              <el-select
                v-model="disk.media_type"
                clearable
                placeholder="盘类型"
                style="width: 110px"
              >
                <el-option
                  v-for="m in DISK_MEDIA_OPTIONS"
                  :key="m.value"
                  :label="m.label"
                  :value="m.value"
                />
              </el-select>
              <el-button type="danger" link @click="removeDiskRow(idx)">删除</el-button>
            </div>
          </el-form-item>
        </div>

        <div class="param-section-title">风扇 / 电源 / RAID</div>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="风扇数量">
              <el-input-number v-model="form.fan_count" :min="0" :max="64" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="风扇型号">
              <el-input v-model="form.fan_model" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="电源(W)">
              <el-input-number v-model="form.psu_power_w" :min="0" :step="100" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="10">
            <el-form-item label="RAID 型号">
              <el-input v-model="form.raid_model" placeholder="如 PERC H755" />
            </el-form-item>
          </el-col>
          <el-col :span="14">
            <el-form-item label="RAID 参数">
              <el-input v-model="form.raid_params" placeholder="如 RAID10 / 缓存 8GB" />
            </el-form-item>
          </el-col>
        </el-row>

        <div class="param-section-title">支持的操作系统</div>
        <el-form-item label="操作系统">
          <div class="os-editor">
            <el-tag
              v-for="os in form.supported_os"
              :key="os"
              closable
              style="margin-right: 6px; margin-bottom: 6px"
              @close="removeOsTag(os)"
            >
              {{ os }}
            </el-tag>
            <div class="os-add">
              <el-input
                v-model="osInput"
                placeholder="输入系统名后添加"
                style="width: 260px"
                @keyup.enter="addOsTag"
              />
              <el-button @click="addOsTag">添加</el-button>
            </div>
          </div>
        </el-form-item>

        <div class="param-section-title">
          <span>自定义参数</span>
          <el-button type="primary" link @click="addCustomRow">+ 手动添加</el-button>
        </div>
        <div v-if="!form.custom.length" class="custom-empty">暂无自定义参数</div>
        <div v-for="(item, idx) in form.custom" :key="idx" class="custom-row">
          <el-input v-model="item.key" placeholder="参数名" style="width: 200px" />
          <el-input v-model="item.value" placeholder="参数值" style="flex: 1" />
          <el-button type="danger" link @click="removeCustomRow(idx)">删除</el-button>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.param-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
}

.param-form {
  max-height: 70vh;
  overflow-y: auto;
  padding-right: 8px;
}

.param-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 12px 0 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.disk-row {
  margin-bottom: 4px;
}

.disk-hint {
  margin: -4px 0 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.disk-fields {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.disk-field-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.os-editor {
  width: 100%;
}

.os-add {
  display: flex;
  gap: 8px;
  margin-top: 6px;
}

.custom-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.custom-empty {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  margin: 0 0 8px 100px;
}
</style>
