<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import TopologyLinkDialog, { type LinkConfirmPayload } from '@/components/TopologyLinkDialog.vue'
import DeviceLocationPickerDialog from '@/components/DeviceLocationPickerDialog.vue'
import { useNetworkTopology } from '@/composables/useNetworkTopology'
import {
  LINK_ROLE_LABELS,
  downloadInterfaceDesignTemplate,
  exportInterfaceDesignExcel,
  importInterfaceDesignExcel,
  type NetworkLink,
  type NetworkLinkRole,
  type NetworkNode,
} from '@/api/network'
import { getDevice } from '@/api/device'
import {
  buildLinkLabels,
  toInterfaceDesignRow,
  type InterfaceDesignRow,
} from '@/utils/interfaceDesign'
import { deviceToNetworkBrief } from '@/utils/deviceBinding'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const {
  projects,
  currentProjectId,
  currentProject,
  currentId,
  currentTopology,
  nodes,
  links,
  loading,
  saving,
  loadProjects,
  selectProject,
  selectTopology,
  saveCanvas,
} = useNetworkTopology()

const canEdit = computed(() => auth.hasPermission('network:update'))
const canMount = computed(() => auth.hasPermission('device:update') || canEdit.value)
const canExport = computed(() => auth.hasPermission('network:view') || canEdit.value)
const linkDialogVisible = ref(false)
const preferredRole = ref<NetworkLinkRole | null>(null)
const editingLink = ref<NetworkLink | null>(null)
const filterRole = ref<'all' | NetworkLinkRole>('all')
const importInput = ref<HTMLInputElement | null>(null)
const excelLoading = ref(false)

const locationVisible = ref(false)
const locationDeviceId = ref<string | null>(null)
const locationDeviceName = ref<string | null>(null)

async function handleExportExcel() {
  if (!currentId.value) {
    ElMessage.warning('请先选择项目/拓扑')
    return
  }
  excelLoading.value = true
  try {
    await exportInterfaceDesignExcel(currentId.value)
    ElMessage.success('已导出接口设计 Excel')
  } catch (err: unknown) {
    const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
    ElMessage.error(msg || '导出失败')
  } finally {
    excelLoading.value = false
  }
}

async function handleDownloadTemplate() {
  excelLoading.value = true
  try {
    await downloadInterfaceDesignTemplate()
  } catch {
    ElMessage.error('下载模板失败')
  } finally {
    excelLoading.value = false
  }
}

function triggerImport() {
  if (!currentId.value) {
    ElMessage.warning('请先选择项目/拓扑')
    return
  }
  importInput.value?.click()
}

async function onImportFileChange(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !currentId.value) return
  excelLoading.value = true
  try {
    const result = await importInterfaceDesignExcel(currentId.value, file)
    await selectTopology(currentId.value, false)
    if (result.failed) {
      ElMessage.warning(
        `导入完成：成功 ${result.created}，失败 ${result.failed}${result.errors?.[0] ? `；${result.errors[0]}` : ''}`,
      )
    } else {
      ElMessage.success(`导入成功：处理 ${result.created} 条连线`)
    }
  } catch (err: unknown) {
    const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
    ElMessage.error(msg || '导入失败')
  } finally {
    excelLoading.value = false
  }
}

const designRows = computed(() =>
  links.value.map((l) => toInterfaceDesignRow(l, nodes.value)).filter((row) => {
    if (filterRole.value === 'all') return true
    return row.linkRole === filterRole.value
  }),
)

async function openLinkDialog() {
  if (!nodes.value.length) {
    ElMessage.warning('请先在「设备定义」中添加设备')
    return
  }
  await hydrateBoundDevices()
  editingLink.value = null
  preferredRole.value = null
  linkDialogVisible.value = true
}

function openEditDialog(row: InterfaceDesignRow) {
  if (!canEdit.value) return
  preferredRole.value = null
  editingLink.value = row.link
  linkDialogVisible.value = true
}

function onDialogClosed() {
  editingLink.value = null
}

watch(linkDialogVisible, (open) => {
  if (!open) onDialogClosed()
})

function nodeById(id: string): NetworkNode | undefined {
  return nodes.value.find((n) => n.id === id)
}

function openLocationEditor(nodeId: string) {
  const node = nodeById(nodeId)
  if (!node) return
  if (!node.device_id) {
    ElMessage.warning('该拓扑设备未关联台账，请先在「添加/编辑连线」中关联设备管理清单，或到「设备定义」绑定')
    return
  }
  if (!canMount.value) {
    ElMessage.warning('无设备上架权限')
    return
  }
  locationDeviceId.value = node.device_id
  locationDeviceName.value = node.name
  locationVisible.value = true
}

/** 位置变更后同步节点简报，并按新位置重算相关连线标签（不整页重载，避免丢失未保存连线） */
async function onLocationSaved() {
  const deviceId = locationDeviceId.value
  if (!deviceId) return
  try {
    const device = await getDevice(deviceId)
    nodes.value.forEach((n) => {
      if (n.device_id !== deviceId) return
      if (!n.device) {
        n.device = {
          device_id: deviceId,
          name: device.name,
          hostname: device.hostname,
          rack_id: device.rack_id,
          room_id: device.room_id,
          rack_code: device.rack_code,
          room_name: device.room_name,
          u_position: device.u_position,
          ip_summary: device.ip_summary,
          bmc_ip: device.bmc_ip ?? null,
          vip: device.vip ?? null,
          device_type_name: device.device_type_name,
          height_u: device.height_u,
        }
      } else {
        n.device.rack_id = device.rack_id
        n.device.room_id = device.room_id
        n.device.rack_code = device.rack_code
        n.device.room_name = device.room_name
        n.device.u_position = device.u_position
        n.device.height_u = device.height_u
      }
    })
    const relatedNodeIds = new Set(
      nodes.value.filter((n) => n.device_id === deviceId).map((n) => n.id),
    )
    links.value.forEach((link) => {
      if (!relatedNodeIds.has(link.source_node_id) && !relatedNodeIds.has(link.target_node_id)) return
      const labels = buildLinkLabels(
        nodeById(link.source_node_id),
        nodeById(link.target_node_id),
        link.source_port,
        link.target_port,
      )
      link.source_label = labels.source_label
      link.target_label = labels.target_label
    })
    ElMessage.info('位置已同步，相关标签已更新，请保存接口设计')
  } catch {
    ElMessage.warning('位置已写入机柜，但刷新显示失败，可重新进入页面')
  }
}

function bindPeerPorts(
  sourceId: string,
  sourcePort: string,
  targetId: string,
  targetPort: string,
  sourceLabel: string | null,
  targetLabel: string | null,
) {
  const source = nodes.value.find((n) => n.id === sourceId)
  const target = nodes.value.find((n) => n.id === targetId)
  if (!source?.port_layout?.ports || !target?.port_layout?.ports) return
  const sp = source.port_layout.ports.find((p) => p.id === sourcePort)
  const tp = target.port_layout.ports.find((p) => p.id === targetPort)
  if (sp) {
    sp.peer_node_id = targetId
    sp.peer_port = targetPort
    sp.peer_label = targetLabel || target.name
  }
  if (tp) {
    tp.peer_node_id = sourceId
    tp.peer_port = sourcePort
    tp.peer_label = sourceLabel || source.name
  }
}

function clearPeerPorts(sourceId: string, sourcePort: string, targetId: string, targetPort: string) {
  const clear = (nodeId: string, portId: string) => {
    const node = nodes.value.find((n) => n.id === nodeId)
    const port = node?.port_layout?.ports?.find((p) => p.id === portId)
    if (!port) return
    port.peer_node_id = null
    port.peer_port = null
    port.peer_label = null
  }
  clear(sourceId, sourcePort)
  clear(targetId, targetPort)
}

function isDuplicate(payload: LinkConfirmPayload, excludeId?: string) {
  return links.value.some((l) => {
    if (excludeId && l.id === excludeId) return false
    return (
      (l.source_node_id === payload.source_node_id &&
        l.source_port === payload.source_port &&
        l.target_node_id === payload.target_node_id &&
        l.target_port === payload.target_port) ||
      (l.source_node_id === payload.target_node_id &&
        l.source_port === payload.target_port &&
        l.target_node_id === payload.source_node_id &&
        l.target_port === payload.source_port)
    )
  })
}

function onLinkConfirm(payload: LinkConfirmPayload) {
  const editing = editingLink.value
  if (isDuplicate(payload, editing?.id)) {
    ElMessage.warning('该接口连线已存在')
    return
  }

  if (editing) {
    // 端口变更时先清旧对端绑定
    if (
      editing.source_node_id !== payload.source_node_id ||
      editing.source_port !== payload.source_port ||
      editing.target_node_id !== payload.target_node_id ||
      editing.target_port !== payload.target_port
    ) {
      clearPeerPorts(
        editing.source_node_id,
        editing.source_port,
        editing.target_node_id,
        editing.target_port,
      )
    }
    editing.link_type = payload.link_type
    editing.source_node_id = payload.source_node_id
    editing.source_port = payload.source_port
    editing.target_node_id = payload.target_node_id
    editing.target_port = payload.target_port
    editing.label = payload.label
    editing.source_label = payload.source_label
    editing.target_label = payload.target_label
    editing.cable_type = payload.cable_type
    editing.interface_class = payload.interface_class
    editing.link_role = payload.link_role
    bindPeerPorts(
      payload.source_node_id,
      payload.source_port,
      payload.target_node_id,
      payload.target_port,
      payload.source_label,
      payload.target_label,
    )
    editingLink.value = null
    ElMessage.success('连线已更新，请保存')
    return
  }

  links.value.push({
    id: crypto.randomUUID(),
    topology_id: currentId.value || '',
    link_type: payload.link_type,
    source_node_id: payload.source_node_id,
    source_port: payload.source_port,
    target_node_id: payload.target_node_id,
    target_port: payload.target_port,
    label: payload.label,
    source_label: payload.source_label,
    target_label: payload.target_label,
    cable_type: payload.cable_type,
    interface_class: payload.interface_class,
    link_role: payload.link_role,
  })
  bindPeerPorts(
    payload.source_node_id,
    payload.source_port,
    payload.target_node_id,
    payload.target_port,
    payload.source_label,
    payload.target_label,
  )
  ElMessage.success('连线已添加，可继续添加；完成后请点「保存」')
}

function clearPeerForLink(row: InterfaceDesignRow) {
  clearPeerPorts(
    row.link.source_node_id,
    row.link.source_port,
    row.link.target_node_id,
    row.link.target_port,
  )
}

function removeLink(row: InterfaceDesignRow) {
  clearPeerForLink(row)
  links.value = links.value.filter((l) => l.id !== row.id)
  ElMessage.success('已删除，请保存')
}

function updateRowField(
  row: InterfaceDesignRow,
  field: 'source_label' | 'target_label' | 'cable_type' | 'interface_class' | 'remark' | 'link_role',
  value: string,
) {
  const link = links.value.find((l) => l.id === row.id)
  if (!link) return
  if (field === 'remark') link.label = value || null
  else if (field === 'source_label') link.source_label = value || null
  else if (field === 'target_label') link.target_label = value || null
  else if (field === 'cable_type') link.cable_type = value || null
  else if (field === 'interface_class') link.interface_class = value || null
  else if (field === 'link_role') link.link_role = value || null
}

async function onProjectChange(id: string) {
  if (!id) return
  await selectProject(id)
  await hydrateBoundDevices()
}

/** 补全已绑定但缺失简报的台账信息（设备名称/型号） */
async function hydrateBoundDevices() {
  const pending = nodes.value.filter((n) => n.device_id && (!n.device || !n.device.name))
  if (!pending.length) return
  await Promise.all(
    pending.map(async (n) => {
      try {
        const d = await getDevice(n.device_id!)
        n.device = deviceToNetworkBrief(d)
      } catch {
        /* ignore */
      }
    }),
  )
}

onMounted(async () => {
  await loadProjects()
  await hydrateBoundDevices()
})

watch(currentId, () => {
  void hydrateBoundDevices()
})
</script>

<template>
  <div class="page" v-loading="loading">
    <el-card shadow="never" class="main-card">
      <section class="workspace">
        <div class="toolbar">
          <span class="title">接口设计</span>
          <el-select
            :model-value="currentProjectId"
            placeholder="选择项目"
            style="width: 200px"
            filterable
            @change="onProjectChange"
          >
            <el-option
              v-for="p in projects"
              :key="p.id"
              :label="`${p.name} (${p.code})`"
              :value="p.id"
            />
          </el-select>
          <span v-if="currentProject" class="meta">项目：{{ currentProject.name }}</span>
          <span v-if="currentTopology" class="meta">拓扑：{{ currentTopology.name }}</span>

          <el-select v-model="filterRole" style="width: 150px" placeholder="筛选场景">
            <el-option label="全部场景" value="all" />
            <el-option
              v-for="(label, key) in LINK_ROLE_LABELS"
              :key="key"
              :label="label"
              :value="key"
            />
          </el-select>

          <div class="spacer" />

          <el-button
            v-if="canExport"
            :loading="excelLoading"
            :disabled="!currentId"
            @click="handleExportExcel"
          >
            导出 Excel
          </el-button>
          <template v-if="canEdit">
            <el-dropdown trigger="click" :disabled="!currentId || excelLoading">
              <el-button :loading="excelLoading" :disabled="!currentId">
                导入 Excel
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="handleDownloadTemplate">下载导入模板</el-dropdown-item>
                  <el-dropdown-item @click="triggerImport">选择文件导入</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <input
              ref="importInput"
              type="file"
              accept=".xlsx,.xls"
              class="hidden-file"
              @change="onImportFileChange"
            />
            <el-button :disabled="!currentId" @click="openLinkDialog()">添加连线</el-button>
            <el-button type="primary" :loading="saving" :disabled="!currentId" @click="saveCanvas">
              保存
            </el-button>
          </template>
        </div>

        <p class="sheet-hint">
          添加连线时可选择场景；本端/对端须已关联设备管理（合同设备名称）。接口来自设备定义面板。
          点击位置/U位可改上架；修改后请保存。
        </p>

        <el-table
          v-if="currentId"
          :data="designRows"
          stripe
          border
          height="calc(100vh - 280px)"
          class="design-sheet"
        >
          <el-table-column label="场景" width="130" fixed>
            <template #default="{ row }: { row: InterfaceDesignRow }">
              <el-select
                v-if="canEdit"
                :model-value="row.linkRole"
                size="small"
                @change="(v: string) => updateRowField(row, 'link_role', v)"
              >
                <el-option
                  v-for="(label, key) in LINK_ROLE_LABELS"
                  :key="key"
                  :label="label"
                  :value="key"
                />
              </el-select>
              <span v-else>{{ row.linkRoleLabel }}</span>
            </template>
          </el-table-column>
          <el-table-column label="本端设备" min-width="110" show-overflow-tooltip>
            <template #default="{ row }">{{ row.sourceKind }}</template>
          </el-table-column>
          <el-table-column label="设备名称" min-width="130" show-overflow-tooltip>
            <template #default="{ row }">{{ row.sourceName }}</template>
          </el-table-column>
          <el-table-column label="设备位置" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <el-button
                v-if="canEdit"
                link
                type="primary"
                @click="openLocationEditor(row.link.source_node_id)"
              >
                {{ row.sourceLocation === '-' ? '设置位置' : row.sourceLocation }}
              </el-button>
              <span v-else>{{ row.sourceLocation }}</span>
            </template>
          </el-table-column>
          <el-table-column label="U位" width="80" align="center">
            <template #default="{ row }">
              <el-button
                v-if="canEdit"
                link
                type="primary"
                @click="openLocationEditor(row.link.source_node_id)"
              >
                {{ row.sourceU === '-' ? '设U' : row.sourceU }}
              </el-button>
              <span v-else>{{ row.sourceU }}</span>
            </template>
          </el-table-column>
          <el-table-column label="本端接口" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ row.sourcePortLabel }}</template>
          </el-table-column>

          <el-table-column label="对端设备" min-width="110" show-overflow-tooltip>
            <template #default="{ row }">{{ row.targetKind }}</template>
          </el-table-column>
          <el-table-column label="设备名称" min-width="130" show-overflow-tooltip>
            <template #default="{ row }">{{ row.targetName }}</template>
          </el-table-column>
          <el-table-column label="对端位置" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <el-button
                v-if="canEdit"
                link
                type="primary"
                @click="openLocationEditor(row.link.target_node_id)"
              >
                {{ row.targetLocation === '-' ? '设置位置' : row.targetLocation }}
              </el-button>
              <span v-else>{{ row.targetLocation }}</span>
            </template>
          </el-table-column>
          <el-table-column label="U位" width="80" align="center">
            <template #default="{ row }">
              <el-button
                v-if="canEdit"
                link
                type="primary"
                @click="openLocationEditor(row.link.target_node_id)"
              >
                {{ row.targetU === '-' ? '设U' : row.targetU }}
              </el-button>
              <span v-else>{{ row.targetU }}</span>
            </template>
          </el-table-column>
          <el-table-column label="对端接口" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ row.targetPortLabel }}</template>
          </el-table-column>

          <el-table-column label="接口类" width="100">
            <template #default="{ row }">
              <el-select
                v-if="canEdit"
                :model-value="row.interfaceClass"
                size="small"
                @change="(v: string) => updateRowField(row, 'interface_class', v)"
              >
                <el-option label="电口" value="electric" />
                <el-option label="光口" value="optical" />
                <el-option label="高速铜缆" value="dac" />
                <el-option label="其他" value="other" />
              </el-select>
              <span v-else>{{ row.interfaceClassLabel }}</span>
            </template>
          </el-table-column>
          <el-table-column label="线缆类" width="130">
            <template #default="{ row }">
              <el-select
                v-if="canEdit"
                :model-value="row.cableType"
                size="small"
                @change="(v: string) => updateRowField(row, 'cable_type', v)"
              >
                <el-option label="超六类铜缆" value="copper_cat6" />
                <el-option label="多模光纤" value="fiber_mm" />
                <el-option label="单模光纤" value="fiber_sm" />
                <el-option label="DAC" value="dac" />
                <el-option label="AOC" value="aoc" />
                <el-option label="其他" value="other" />
              </el-select>
              <span v-else>{{ row.cableTypeLabel }}</span>
            </template>
          </el-table-column>
          <el-table-column label="本端标签" min-width="180">
            <template #default="{ row }">
              <el-input
                v-if="canEdit"
                :model-value="row.sourceLabel"
                size="small"
                @change="(v: string) => updateRowField(row, 'source_label', v)"
              />
              <span v-else>{{ row.sourceLabel }}</span>
            </template>
          </el-table-column>
          <el-table-column label="对端标签" min-width="180">
            <template #default="{ row }">
              <el-input
                v-if="canEdit"
                :model-value="row.targetLabel"
                size="small"
                @change="(v: string) => updateRowField(row, 'target_label', v)"
              />
              <span v-else>{{ row.targetLabel }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <template v-if="canEdit">
                <el-button type="primary" link @click="openEditDialog(row)">编辑</el-button>
                <el-button type="danger" link @click="removeLink(row)">删除</el-button>
              </template>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="请先在「设备定义」中创建或选择项目" />
      </section>
    </el-card>

    <TopologyLinkDialog
      v-model="linkDialogVisible"
      :nodes="nodes"
      :links="links"
      :preferred-role="preferredRole"
      :editing-link="editingLink"
      @confirm="onLinkConfirm"
    />

    <DeviceLocationPickerDialog
      v-model="locationVisible"
      :device-id="locationDeviceId"
      :device-name="locationDeviceName"
      @saved="onLocationSaved"
    />
  </div>
</template>

<style scoped>
.page {
  height: calc(100vh - 180px);
}

.main-card {
  height: 100%;
}

.main-card :deep(.el-card__body) {
  height: 100%;
  padding: 12px 16px;
}

.workspace {
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.title {
  font-weight: 600;
}

.meta {
  color: #909399;
  font-size: 13px;
}

.spacer {
  flex: 1;
}

.hidden-file {
  display: none;
}

.sheet-hint {
  margin: 0 0 8px;
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}

.design-sheet :deep(.el-table__header th) {
  background: #f5f7fa;
  color: #303133;
  font-weight: 600;
}
</style>
