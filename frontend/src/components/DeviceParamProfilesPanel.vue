<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createDeviceType,
  createParamProfile,
  deleteParamProfile,
  downloadParamProfilesTemplate,
  exportParamProfiles,
  importParamProfiles,
  listDeviceTypes,
  listParamProfiles,
  syncParamProfilesFromContracts,
  updateDeviceType,
  updateParamProfile,
  type DeviceType,
  type DiskRole,
  type ParamDiskSpec,
  type ParamProfile,
  type ParamProfilePayload,
} from '@/api/device'
import { getContractSummary } from '@/api/contract'
import { useAuthStore } from '@/stores/auth'
import {
  DEVICE_TYPE_CODES,
  DEVICE_TYPE_FALLBACK_NAMES,
  buildDeviceTypeOptions,
  displayDeviceTypeName,
  type DeviceTypeCode,
} from '@/utils/deviceTypeCatalog'

const auth = useAuthStore()
const canUpdate = auth.hasPermission('device:update')
const canCreate = auth.hasPermission('device:create')
const canDelete = auth.hasPermission('device:delete') || canUpdate

const loading = ref(false)
const syncing = ref(false)
const exporting = ref(false)
const importing = ref(false)
const saving = ref(false)
const profiles = ref<ParamProfile[]>([])
const deviceTypes = ref<DeviceType[]>([])
/** 采购汇总设备名称（小写）集合，用于展示关联状态 */
const summaryNameKeys = ref<Set<string>>(new Set())
const dialogVisible = ref(false)
const editingId = ref<string | null>(null)
const editingPayload = ref<ParamProfilePayload | null>(null)
const importInput = ref<HTMLInputElement | null>(null)

/** 与设备管理同一组设备类型（标准名称 + 下拉样式） */
const deviceTypeOptions = computed(() => buildDeviceTypeOptions(deviceTypes.value))

const filters = reactive({
  keyword: '',
  status: 'all' as 'all' | 'incomplete' | 'complete',
  manufacturer: '',
  device_type_id: '',
})

const DISK_INTERFACE_OPTIONS = ['SATA', 'SAS', 'NVMe', 'PCIe', 'M.2', 'U.2']
const DISK_MEDIA_OPTIONS = [
  { value: 'ssd', label: 'SSD' },
  { value: 'hdd', label: '机械盘' },
  { value: 'nvme', label: 'NVMe' },
]
const MAX_DISK_SPEC_COUNT = 20

function emptyDisk(role: DiskRole): ParamDiskSpec {
  return { size_gb: null, count: null, interface: null, media_type: null, role }
}

const form = reactive({
  code: '',
  name: '',
  description: '',
  device_type_id: '' as string,
  source_device_model: '',
  detail_params: '',
  source_manufacturer: '',
  systemDisk: emptyDisk('system'),
  dataDisks: [emptyDisk('data'), emptyDisk('data')] as ParamDiskSpec[],
  other_params: '',
})

function isDiskRowFilled(d: ParamDiskSpec): boolean {
  return d.size_gb != null || d.count != null || !!d.interface || !!d.media_type
}

function deviceTypeName(typeId: string | null | undefined) {
  return displayDeviceTypeName(deviceTypes.value, typeId)
}

async function ensureDeviceTypeOption(code: DeviceTypeCode) {
  const existed = deviceTypes.value.find((t) => t.code === code)
  if (existed) return existed
  const created = await createDeviceType({
    code,
    name: DEVICE_TYPE_FALLBACK_NAMES[code],
    description: DEVICE_TYPE_FALLBACK_NAMES[code],
  })
  deviceTypes.value = [...deviceTypes.value, created].sort((a, b) =>
    a.code.localeCompare(b.code),
  )
  return created
}

async function onParamDeviceTypePick(typeId: string | null) {
  if (!typeId) {
    form.device_type_id = ''
    return
  }
  const opt = deviceTypeOptions.value.find((o) => o.id === typeId || o.code === typeId)
  if (opt?.missing) {
    const created = await ensureDeviceTypeOption(opt.code)
    form.device_type_id = created.id
    return
  }
  form.device_type_id = typeId
}

/** 将库中旧短名同步为与设备管理一致的标准名称，并补齐缺失类型 */
async function syncCanonicalDeviceTypes() {
  const byCode = new Map(deviceTypes.value.map((t) => [t.code, t]))
  for (const code of DEVICE_TYPE_CODES) {
    const want = DEVICE_TYPE_FALLBACK_NAMES[code]
    const hit = byCode.get(code)
    if (!hit) {
      try {
        const created = await createDeviceType({ code, name: want, description: want })
        deviceTypes.value = [...deviceTypes.value, created]
        byCode.set(code, created)
      } catch {
        // ignore
      }
      continue
    }
    if (hit.name !== want) {
      try {
        const updated = await updateDeviceType(hit.id, { name: want, description: want })
        deviceTypes.value = deviceTypes.value.map((t) => (t.id === updated.id ? updated : t))
        byCode.set(code, updated)
      } catch {
        // ignore
      }
    }
  }
}

function detailOf(row: ParamProfile) {
  return row.detail_params || row.payload?.detail_params || ''
}

function modelOf(row: ParamProfile) {
  return row.source_device_model || row.payload?.source_device_model || ''
}

function typeIdOf(row: ParamProfile) {
  return row.device_type_id || row.payload?.device_type_id || ''
}

function profileNameKey(row: ParamProfile) {
  return (row.source_device_name || row.payload?.source_device_name || row.name || '')
    .trim()
    .toLowerCase()
}

function isLinkedToSummary(row: ParamProfile) {
  const key = profileNameKey(row)
  return !!key && summaryNameKeys.value.has(key)
}

async function loadSummaryNames() {
  try {
    const summary = await getContractSummary()
    const keys = new Set<string>()
    for (const row of summary || []) {
      const name = (row.device_name || '').trim().toLowerCase()
      if (name) keys.add(name)
    }
    summaryNameKeys.value = keys
  } catch {
    summaryNameKeys.value = new Set()
  }
}

function legacyOtherParams(p: ParamProfilePayload): string {
  if (p.other_params?.trim()) return p.other_params
  const lines: string[] = []
  const fanBits = [
    p.fan_count != null ? `${p.fan_count}个` : '',
    p.fan_model || '',
  ].filter(Boolean)
  if (fanBits.length) lines.push(`风扇: ${fanBits.join(' ')}`)
  if (p.psu_power_w != null) lines.push(`电源: ${p.psu_power_w}W`)
  const raidBits = [p.raid?.model || '', p.raid?.params || ''].filter(Boolean)
  if (raidBits.length) lines.push(`RAID: ${raidBits.join(' / ')}`)
  if (p.supported_os?.length) lines.push(`操作系统: ${p.supported_os.join(', ')}`)
  return lines.join('\n')
}

function makeCode(deviceName: string): string {
  let hash = 0
  const text = deviceName || 'device'
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash << 5) - hash + text.charCodeAt(i)
    hash |= 0
  }
  const digest = Math.abs(hash).toString(16).padStart(8, '0').slice(0, 8)
  const ascii = text
    .normalize('NFKD')
    .replace(/[^\x00-\x7F]/g, '')
    .replace(/[^A-Za-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
  const slug = ascii || 'dev'
  return `P-${slug.slice(0, 24)}-${digest}`.slice(0, 50)
}

function resetForm() {
  form.code = ''
  form.name = ''
  form.description = ''
  form.device_type_id = ''
  form.source_device_model = ''
  form.detail_params = ''
  form.source_manufacturer = ''
  form.systemDisk = emptyDisk('system')
  form.dataDisks = [emptyDisk('data'), emptyDisk('data')]
  form.other_params = ''
  editingPayload.value = null
}

function fillForm(row: ParamProfile) {
  const p = row.payload || {}
  editingPayload.value = p
  form.code = row.code
  form.name = row.name
  form.description = row.description || ''
  form.device_type_id = typeIdOf(row)
  form.source_device_model = modelOf(row)
  form.detail_params = detailOf(row)
  form.source_manufacturer = p.source_manufacturer || row.source_manufacturer || ''

  const disks = [...(p.disks || [])]
  const system = disks.find((d) => d.role === 'system')
  const dataRows = disks.filter((d) => d.role === 'data')
  const legacy = disks.filter((d) => !d.role)
  if (system || dataRows.length) {
    form.systemDisk = system
      ? { ...emptyDisk('system'), ...system, role: 'system' }
      : emptyDisk('system')
    form.dataDisks = dataRows.length
      ? dataRows.map((d) => ({ ...emptyDisk('data'), ...d, role: 'data' as const }))
      : [emptyDisk('data'), emptyDisk('data')]
  } else if (legacy.length) {
    form.systemDisk = { ...emptyDisk('system'), ...legacy[0], role: 'system' }
    form.dataDisks = legacy.slice(1).length
      ? legacy.slice(1).map((d) => ({ ...emptyDisk('data'), ...d, role: 'data' as const }))
      : [emptyDisk('data')]
  } else {
    form.systemDisk = emptyDisk('system')
    form.dataDisks = [emptyDisk('data'), emptyDisk('data')]
  }

  form.other_params = legacyOtherParams(p)
}

function buildPayload(): ParamProfilePayload {
  const dataDisks = form.dataDisks
    .filter(isDiskRowFilled)
    .map((d) => ({
      size_gb: d.size_gb,
      count: d.count,
      interface: d.interface || null,
      media_type: d.media_type || null,
      role: 'data' as const,
    }))
  const disks: ParamDiskSpec[] = []
  if (isDiskRowFilled(form.systemDisk)) {
    disks.push({
      size_gb: form.systemDisk.size_gb,
      count: form.systemDisk.count,
      interface: form.systemDisk.interface || null,
      media_type: form.systemDisk.media_type || null,
      role: 'system',
    })
  } else {
    disks.push({ role: 'system' })
  }
  if (dataDisks.length) disks.push(...dataDisks)
  else disks.push({ role: 'data' })

  const model = form.source_device_model.trim()
  const detail = form.detail_params.trim()
  const prev = editingPayload.value
  return {
    source_device_name: form.name || null,
    source_device_model: model || null,
    source_manufacturer: form.source_manufacturer.trim() || null,
    device_type_id: form.device_type_id || null,
    detail_params: detail || null,
    other_params: form.other_params.trim() || null,
    // 保留历史 CPU/内存数据，表单不再编辑
    cpu: prev?.cpu ?? null,
    memory: prev?.memory ?? null,
    disks,
    // 风扇/电源/RAID/OS 已合并到 other_params
    fan_count: null,
    fan_model: null,
    psu_power_w: null,
    raid: null,
    supported_os: [],
    custom: [],
  }
}

function addDataDiskRow() {
  if (form.dataDisks.length >= MAX_DISK_SPEC_COUNT - 1) {
    ElMessage.warning(`最多添加 ${MAX_DISK_SPEC_COUNT - 1} 种数据盘规格`)
    return
  }
  form.dataDisks.push(emptyDisk('data'))
}

function removeDataDiskRow(idx: number) {
  if (form.dataDisks.length <= 1) {
    form.dataDisks[0] = emptyDisk('data')
    return
  }
  form.dataDisks.splice(idx, 1)
}

const manufacturerOptions = computed(() => {
  const set = new Set<string>()
  for (const row of profiles.value) {
    const m = row.source_manufacturer || row.payload?.source_manufacturer
    if (m) set.add(m)
  }
  return [...set].sort()
})

const filteredProfiles = computed(() => {
  const kw = filters.keyword.trim().toLowerCase()
  return profiles.value.filter((row) => {
    if (filters.status === 'complete' && !row.is_complete) return false
    if (filters.status === 'incomplete' && row.is_complete) return false
    if (filters.manufacturer) {
      const m = row.source_manufacturer || row.payload?.source_manufacturer || ''
      if (m !== filters.manufacturer) return false
    }
    if (filters.device_type_id && typeIdOf(row) !== filters.device_type_id) return false
    if (!kw) return true
    const hay = [
      row.name,
      modelOf(row),
      detailOf(row),
      deviceTypeName(typeIdOf(row)),
      row.source_manufacturer,
      row.summary,
      row.description,
      ...(row.missing_fields || []),
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return hay.includes(kw)
  })
})

const stats = computed(() => {
  const total = profiles.value.length
  const incomplete = profiles.value.filter((p) => !p.is_complete).length
  return { total, incomplete, complete: total - incomplete }
})

function rowClassName({ row }: { row: ParamProfile }) {
  return row.is_complete ? 'row-complete' : 'row-incomplete'
}

async function loadDeviceTypes() {
  try {
    deviceTypes.value = await listDeviceTypes()
    await syncCanonicalDeviceTypes()
  } catch {
    deviceTypes.value = []
  }
}

async function loadData(opts?: { silent?: boolean }) {
  loading.value = true
  try {
    const [list] = await Promise.all([listParamProfiles(), loadSummaryNames()])
    profiles.value = list
  } catch {
    profiles.value = []
    if (!opts?.silent) ElMessage.error('加载设备参数失败')
  } finally {
    loading.value = false
  }
}

async function handleSync() {
  syncing.value = true
  try {
    const result = await syncParamProfilesFromContracts()
    if (result.total_summary === 0) {
      ElMessage.warning('采购汇总中暂无设备名称可同步')
    } else if (result.created === 0 && result.updated === 0 && result.skipped > 0) {
      ElMessage.info(`采购汇总设备名称均已关联，已对齐 ${result.skipped} 项`)
    } else {
      const parts = [
        result.created ? `新建 ${result.created}` : '',
        result.updated ? `同步 ${result.updated}` : '',
        result.skipped ? `已对齐 ${result.skipped}` : '',
      ].filter(Boolean)
      ElMessage.success(`关联同步完成：${parts.join('，')}`)
    }
    await loadData({ silent: true })
  } catch (error: unknown) {
    const err = error as {
      response?: { status?: number; data?: { message?: string } }
      message?: string
    }
    const detail = err.response?.data?.message || err.message
    ElMessage.error(detail ? `同步采购汇总失败：${detail}` : '同步采购汇总失败')
  } finally {
    syncing.value = false
  }
}

async function handleExport(incompleteOnly: boolean) {
  exporting.value = true
  try {
    await exportParamProfiles(incompleteOnly)
    ElMessage.success(incompleteOnly ? '已导出未完善参数' : '已导出全部参数')
  } catch {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

async function handleDownloadTemplate() {
  try {
    await downloadParamProfilesTemplate()
  } catch {
    ElMessage.error('模板下载失败')
  }
}

function triggerImport() {
  importInput.value?.click()
}

async function handleImportFile(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  importing.value = true
  try {
    const result = await importParamProfiles(file)
    const errHint = result.errors?.length ? `；错误 ${result.errors.length} 条` : ''
    ElMessage.success(
      `导入完成：更新 ${result.updated}，新建 ${result.created}，跳过 ${result.skipped}${errHint}`,
    )
    if (result.errors?.length) {
      console.warn('参数导入错误', result.errors)
    }
    await loadData({ silent: true })
  } catch {
    ElMessage.error('导入失败')
  } finally {
    importing.value = false
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

/** 新建时若尚未手填设备参数ID，随名称自动生成建议值 */
function onNameChangeForCode() {
  if (editingId.value) return
  const name = form.name.trim()
  if (!name) return
  if (!form.code.trim()) {
    form.code = makeCode(name)
  }
}

async function handleSave() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写设备名称')
    return
  }
  const code = form.code.trim() || makeCode(form.name.trim())
  if (!code) {
    ElMessage.warning('请填写设备参数ID')
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    if (editingId.value) {
      await updateParamProfile(editingId.value, {
        code,
        name: form.name.trim(),
        payload,
        description: form.description || null,
      })
    } else {
      await createParamProfile({
        code,
        name: form.name.trim(),
        payload,
        description: form.description || null,
      })
    }
    ElMessage.success('设备参数已保存')
    dialogVisible.value = false
    await loadData({ silent: true })
  } catch (error: unknown) {
    const err = error as {
      response?: { data?: { message?: string } }
      message?: string
    }
    ElMessage.error(err.response?.data?.message || err.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: ParamProfile) {
  await ElMessageBox.confirm(`确定删除设备参数「${row.name}」吗？`, '确认删除', { type: 'warning' })
  await deleteParamProfile(row.id)
  ElMessage.success('已删除')
  await loadData({ silent: true })
}

onMounted(async () => {
  await Promise.all([loadData(), loadDeviceTypes()])
  if (canUpdate) {
    try {
      const result = await syncParamProfilesFromContracts()
      if (result.created > 0 || result.updated > 0) {
        await loadData({ silent: true })
      }
    } catch {
      /* 采购汇总为空或无权限时忽略自动同步 */
    }
  }
})
</script>

<template>
  <div class="param-panel">
    <div class="stats-bar">
      <span>共 {{ stats.total }} 项</span>
      <span class="stat-incomplete">待完善 {{ stats.incomplete }}</span>
      <span class="stat-complete">已完善 {{ stats.complete }}</span>
      <span class="hint">
        与采购汇总按「设备名称」关联同步：缺则新建、同名则对齐名称/型号/厂商
      </span>
    </div>

    <div class="toolbar">
      <el-input
        v-model="filters.keyword"
        clearable
        size="small"
        placeholder="搜索设备名称 / 详细参数 / 类型 / 摘要"
        style="width: 240px"
      />
      <el-select v-model="filters.status" size="small" style="width: 120px">
        <el-option label="全部状态" value="all" />
        <el-option label="待完善" value="incomplete" />
        <el-option label="已完善" value="complete" />
      </el-select>
      <el-select
        v-model="filters.device_type_id"
        clearable
        size="small"
        placeholder="设备类型"
        style="width: 160px"
      >
        <el-option
          v-for="t in deviceTypeOptions.filter((o) => o.id)"
          :key="t.code"
          :label="t.name"
          :value="t.id"
        />
      </el-select>
      <el-select
        v-model="filters.manufacturer"
        clearable
        size="small"
        placeholder="厂商"
        style="width: 130px"
      >
        <el-option v-for="m in manufacturerOptions" :key="m" :label="m" :value="m" />
      </el-select>
      <el-button size="small" :loading="loading" @click="loadData()">刷新</el-button>
      <el-button
        v-if="canUpdate || canCreate"
        size="small"
        type="primary"
        plain
        :loading="syncing"
        @click="handleSync"
      >
        同步采购汇总
      </el-button>
      <el-dropdown v-if="canUpdate || canCreate" trigger="click" @command="(c: string) => handleExport(c === 'incomplete')">
        <el-button size="small" :loading="exporting">导出 Excel</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="incomplete">仅未完善参数</el-dropdown-item>
            <el-dropdown-item command="all">全部参数</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-button size="small" @click="handleDownloadTemplate">下载模板</el-button>
      <el-button
        v-if="canUpdate || canCreate"
        size="small"
        :loading="importing"
        @click="triggerImport"
      >
        导入更新
      </el-button>
      <el-button v-if="canCreate || canUpdate" type="primary" size="small" @click="openCreate">
        手动新建
      </el-button>
      <input
        ref="importInput"
        type="file"
        accept=".xlsx,.xls"
        style="display: none"
        @change="handleImportFile"
      />
    </div>

    <el-table
      v-loading="loading"
      :data="filteredProfiles"
      stripe
      size="small"
      max-height="520"
      :row-class-name="rowClassName"
    >
      <el-table-column
        type="index"
        label="序号"
        width="64"
        align="center"
        :index="(i: number) => i + 1"
      />
      <el-table-column prop="name" label="设备名称" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">
          <span :class="row.is_complete ? 'text-complete' : 'text-incomplete'">{{ row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="采购关联" width="110" align="center">
        <template #default="{ row }">
          <el-tag
            :type="isLinkedToSummary(row) ? 'success' : 'info'"
            size="small"
            effect="plain"
          >
            {{ isLinkedToSummary(row) ? '已关联' : '未在汇总' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="code" label="设备参数ID" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">
          <span :class="row.is_complete ? 'text-complete' : 'text-incomplete'">{{ row.code }}</span>
        </template>
      </el-table-column>
      <el-table-column label="配置摘要" min-width="240" show-overflow-tooltip>
        <template #default="{ row }">
          <span :class="row.is_complete ? 'text-complete' : 'text-incomplete'">
            {{ row.summary || '待补充系统盘 / 数据盘' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="设备类型" min-width="120" show-overflow-tooltip>
        <template #default="{ row }">
          <span :class="row.is_complete ? 'text-complete' : 'text-incomplete'">
            {{ deviceTypeName(typeIdOf(row)) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="设备型号" min-width="120" show-overflow-tooltip>
        <template #default="{ row }">
          <span :class="row.is_complete ? 'text-complete' : 'text-incomplete'">
            {{ modelOf(row) || '—' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="厂商" min-width="90" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.source_manufacturer || row.payload?.source_manufacturer || '—' }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_complete ? 'success' : 'danger'" size="small" effect="plain">
            {{ row.is_complete ? '已完善' : '待完善' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="缺失字段" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.missing_fields?.length" class="text-incomplete">
            {{ row.missing_fields.join('、') }}
          </span>
          <span v-else class="text-complete">—</span>
        </template>
      </el-table-column>
      <el-table-column label="详细参数" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <span :class="row.is_complete ? 'text-complete' : 'text-incomplete'">
            {{ detailOf(row) || '—' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="88" fixed="right" align="center">
        <template #default="{ row }">
          <el-dropdown trigger="click">
            <el-button type="primary" link>操作</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-if="canUpdate" @click="openEdit(row)">编辑</el-dropdown-item>
                <el-dropdown-item v-if="canDelete" divided @click="handleDelete(row)">删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑设备参数' : '新建设备参数'"
      width="820px"
      destroy-on-close
      top="3vh"
    >
      <el-form label-width="100px" class="param-form" size="small">
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="设备名称" required>
              <el-input
                v-model="form.name"
                placeholder="对应采购汇总设备名称"
                @change="onNameChangeForCode"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="设备参数ID" required>
              <el-input
                v-model="form.code"
                maxlength="50"
                placeholder="唯一设备参数ID，可手动修改"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="设备型号">
              <el-input v-model="form.source_device_model" placeholder="设备型号" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="设备类型">
              <el-select
                :model-value="form.device_type_id || undefined"
                clearable
                filterable
                placeholder="选择设备类型"
                style="width: 100%"
                @change="onParamDeviceTypePick"
              >
                <el-option
                  v-for="t in deviceTypeOptions"
                  :key="t.code"
                  :label="t.name"
                  :value="t.id || t.code"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="厂商">
              <el-input v-model="form.source_manufacturer" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="描述">
              <el-input v-model="form.description" placeholder="可选备注" />
            </el-form-item>
          </el-col>
        </el-row>

        <div class="param-section-title">系统盘</div>
        <div class="disk-row">
          <div class="disk-fields">
            <el-input-number
              v-model="form.systemDisk.size_gb"
              :min="0"
              :step="100"
              placeholder="容量GB"
              controls-position="right"
            />
            <span class="disk-field-label">GB ×</span>
            <el-input-number
              v-model="form.systemDisk.count"
              :min="0"
              :max="100"
              placeholder="块数"
              controls-position="right"
            />
            <span class="disk-field-label">块</span>
            <el-select
              v-model="form.systemDisk.interface"
              clearable
              allow-create
              filterable
              placeholder="接口"
              style="width: 110px"
            >
              <el-option v-for="i in DISK_INTERFACE_OPTIONS" :key="i" :label="i" :value="i" />
            </el-select>
            <el-select
              v-model="form.systemDisk.media_type"
              clearable
              placeholder="介质"
              style="width: 110px"
            >
              <el-option
                v-for="m in DISK_MEDIA_OPTIONS"
                :key="m.value"
                :label="m.label"
                :value="m.value"
              />
            </el-select>
          </div>
        </div>

        <div class="param-section-title">
          <span>数据盘</span>
          <el-button type="primary" link @click="addDataDiskRow">+ 添加规格</el-button>
        </div>
        <p class="disk-hint">可配置多组数据盘规格。</p>
        <div v-for="(disk, idx) in form.dataDisks" :key="idx" class="disk-row">
          <el-form-item :label="`规格 ${idx + 1}`" label-width="70px">
            <div class="disk-fields">
              <el-input-number
                v-model="disk.size_gb"
                :min="0"
                :step="100"
                placeholder="容量GB"
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
                placeholder="介质"
                style="width: 110px"
              >
                <el-option
                  v-for="m in DISK_MEDIA_OPTIONS"
                  :key="m.value"
                  :label="m.label"
                  :value="m.value"
                />
              </el-select>
              <el-button type="danger" link @click="removeDataDiskRow(idx)">删除</el-button>
            </div>
          </el-form-item>
        </div>

        <div class="param-section-title">详细参数</div>
        <el-input
          v-model="form.detail_params"
          type="textarea"
          :rows="3"
          maxlength="1000"
          show-word-limit
          placeholder="填写详细参数说明，如配置备注等"
        />

        <div class="param-section-title">其他参数</div>
        <el-input
          v-model="form.other_params"
          type="textarea"
          :rows="3"
          maxlength="3000"
          show-word-limit
          placeholder="可选。风扇、电源、RAID、操作系统等可写在这里"
        />
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
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

.stats-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  font-size: 12px;
  color: #5b6b7c;
}

.stat-incomplete {
  color: #c45656;
  font-weight: 600;
}

.stat-complete {
  color: #303133;
  font-weight: 600;
}

.hint {
  color: #8a97a8;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.text-incomplete {
  color: #c45656;
}

.text-complete {
  color: #303133;
}

:deep(.row-incomplete td) {
  color: #c45656;
}

:deep(.row-complete td) {
  color: #303133;
}

.param-form {
  max-height: 72vh;
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

</style>
