<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import NetworkDeviceFrameEditor from '@/components/NetworkDeviceFrameEditor.vue'
import { useNetworkTopology } from '@/composables/useNetworkTopology'
import {
  CORE_CARD_TYPE_LABELS,
  NODE_KIND_LABELS,
  SERVER_FORM_FACTOR_LABELS,
  SWITCH_SUBTYPE_DEFAULTS,
  SWITCH_SUBTYPE_LABELS,
  UPLINK_POSITION_LABELS,
  newCoreLineCard,
  type CoreCardType,
  type CoreLineCard,
  type NetworkNode,
  type NetworkNodeKind,
  type ServerFormFactor,
  type SwitchSubtype,
  type UplinkPosition,
} from '@/api/network'
import { listDevices, type Device } from '@/api/device'
import { useAuthStore } from '@/stores/auth'
import {
  applySecurityLayoutConfig,
  applySwitchLayoutConfig,
  defaultPortLayout,
  ensurePortLayout,
  generatePortsFromSlotsDef,
  RACK_WIDTH_MM,
  syncLegacyFromPortLayout,
  syncLinksFromPortLayout,
} from '@/utils/networkPortLayout'
import { normalizeGigabitUplinkCount, normalizeTenGigabitUplinkCount } from '@/utils/switchFrontPanel'
import { applyServerFormFactor, defaultServerSlotsDef } from '@/utils/serverRearPanel'
import { SEC_FRAME_HEIGHT_BY_U, defaultSecurityZones } from '@/utils/securityFrontPanel'

const router = useRouter()
const auth = useAuthStore()
const {
  currentId,
  nodes,
  links,
  loading,
  saving,
  loadTopologies,
  saveCanvas,
} = useNetworkTopology()

const canEdit = computed(() => auth.hasPermission('network:update'))
const deviceOptions = ref<Device[]>([])
const deviceLoading = ref(false)
const selectedNodeId = ref<string | null>(null)
const basicVisible = ref(false)
const basicForm = reactive({
  kind: 'switch' as NetworkNodeKind,
  name: '',
  device_id: null as string | null,
  switch_subtype: 'gigabit' as SwitchSubtype,
  main_port_count: 48,
  uplink_port_count: 4,
  uplink_position: 'right' as UplinkPosition,
  line_cards: [newCoreLineCard('ten_gigabit', 48)] as CoreLineCard[],
  server_form_factor: 1 as ServerFormFactor,
  security_height_u: 1,
})

const isCoreSwitch = computed(() => basicForm.kind === 'switch' && basicForm.switch_subtype === 'core')
const isGigabitSwitch = computed(() => basicForm.kind === 'switch' && basicForm.switch_subtype === 'gigabit')
const isTenGigabitSwitch = computed(() => basicForm.kind === 'switch' && basicForm.switch_subtype === 'ten_gigabit')
const isCreateServer = computed(() => basicForm.kind === 'server')
const isCreateSecurity = computed(() => basicForm.kind === 'security')

const selectedNode = computed(
  () => nodes.value.find((n) => n.id === selectedNodeId.value) || null,
)

const peerNodes = computed(() =>
  nodes.value.filter((n) => n.id !== selectedNodeId.value),
)

function openCreate(kind: NetworkNodeKind) {
  if (!currentId.value) {
    ElMessage.warning('请先在「拓扑设计」中创建拓扑')
    return
  }
  basicForm.kind = kind
  basicForm.name = `${NODE_KIND_LABELS[kind]}${nodes.value.filter((n) => n.kind === kind).length + 1}`
  basicForm.device_id = null
  if (kind === 'switch') {
    basicForm.switch_subtype = 'gigabit'
    basicForm.main_port_count = 48
    basicForm.uplink_port_count = 4
    basicForm.uplink_position = 'right'
    basicForm.line_cards = [newCoreLineCard('ten_gigabit', 48)]
    lastCreateUplinkCount.value = 4
  }
  if (kind === 'server') {
    basicForm.server_form_factor = 1
  }
  if (kind === 'security') {
    basicForm.security_height_u = 1
  }
  basicVisible.value = true
}

function onSwitchSubtypeChange(subtype: SwitchSubtype) {
  const defaults = SWITCH_SUBTYPE_DEFAULTS[subtype]
  basicForm.main_port_count = defaults.mainPortCount
  basicForm.uplink_port_count = defaults.uplinkPortCount
  lastCreateUplinkCount.value = defaults.uplinkPortCount
  if (subtype === 'core' && !basicForm.line_cards.length) {
    basicForm.line_cards = [newCoreLineCard('ten_gigabit', 48)]
  }
}

const lastCreateUplinkCount = ref(4)

function onCreateGigabitUplinkChange(val: number | undefined) {
  if (val == null) return
  const next = normalizeGigabitUplinkCount(val, lastCreateUplinkCount.value)
  basicForm.uplink_port_count = next
  lastCreateUplinkCount.value = next
}

function onCreateTenGigabitUplinkChange(val: number | undefined) {
  if (val == null) return
  const next = normalizeTenGigabitUplinkCount(val, lastCreateUplinkCount.value)
  basicForm.uplink_port_count = next
  lastCreateUplinkCount.value = next
}

function addLineCard() {
  if (basicForm.line_cards.length >= 16) return
  basicForm.line_cards.push(newCoreLineCard('ten_gigabit', 48))
}

function removeLineCard(idx: number) {
  if (basicForm.line_cards.length <= 1) return
  basicForm.line_cards.splice(idx, 1)
}

function onCreateLineCardTypeChange(card: CoreLineCard) {
  if (card.card_type === 'blank') card.port_count = 0
  else if (!card.port_count || card.port_count < 1) card.port_count = 48
}

function confirmCreate() {
  if (!basicForm.name.trim() || !currentId.value) return
  if (basicForm.kind === 'switch' && basicForm.switch_subtype === 'core' && !basicForm.line_cards.length) {
    ElMessage.warning('请至少定义一块板卡')
    return
  }
  const securityHeightU = basicForm.kind === 'security' && Number(basicForm.security_height_u) >= 2 ? 2 : 1
  if (basicForm.kind === 'security') basicForm.security_height_u = securityHeightU

  const portLayout =
    basicForm.kind === 'security'
      ? defaultPortLayout('security', RACK_WIDTH_MM, securityHeightU)
      : defaultPortLayout(basicForm.kind)

  if (basicForm.kind === 'switch') {
    const uplinkCount =
      basicForm.switch_subtype === 'gigabit'
        ? normalizeGigabitUplinkCount(basicForm.uplink_port_count)
        : basicForm.switch_subtype === 'ten_gigabit'
          ? normalizeTenGigabitUplinkCount(basicForm.uplink_port_count)
          : basicForm.uplink_port_count
    basicForm.uplink_port_count = uplinkCount
    applySwitchLayoutConfig(portLayout, {
      subtype: basicForm.switch_subtype,
      mainPortCount: basicForm.main_port_count,
      uplinkPortCount: uplinkCount,
      uplinkPosition: basicForm.uplink_position,
      lineCards: basicForm.switch_subtype === 'core' ? basicForm.line_cards : [],
    })
  } else if (basicForm.kind === 'server') {
    applyServerFormFactor(portLayout, basicForm.server_form_factor)
    portLayout.slots_def = defaultServerSlotsDef(basicForm.server_form_factor)
    portLayout.slot_count = portLayout.slots_def.length
    portLayout.server_panel_side = 'rear'
    portLayout.server_onboard_1g_count = 4
    generatePortsFromSlotsDef(portLayout, false)
  } else if (basicForm.kind === 'security') {
    applySecurityLayoutConfig(portLayout, {
      heightU: securityHeightU,
      zones: defaultSecurityZones(),
      preservePeers: false,
    })
    // 强制落盘高度，避免后续归一化覆盖
    portLayout.height_u = securityHeightU
    portLayout.frame_height = SEC_FRAME_HEIGHT_BY_U[securityHeightU as 1 | 2]
    portLayout.security_panel = true
  } else {
    generatePortsFromSlotsDef(portLayout, false)
  }
  portLayout.layout_locked = false
  const node: NetworkNode = {
    id: crypto.randomUUID(),
    topology_id: currentId.value,
    kind: basicForm.kind,
    name: basicForm.name.trim(),
    device_id: basicForm.device_id,
    pos_x: 80 + (nodes.value.length % 6) * 180,
    pos_y: 80 + Math.floor(nodes.value.length / 6) * 120,
    switch_port_count: portLayout.ports.length,
    slots: null,
    port_layout: portLayout,
    device: null,
  }
  syncLegacyFromPortLayout(node)
  nodes.value.push(node)
  selectNode(node)
  basicVisible.value = false
}

function selectNode(node: NetworkNode) {
  selectedNodeId.value = node.id
  node.port_layout = ensurePortLayout(node)
}

function removeNode(node: NetworkNode) {
  nodes.value = nodes.value.filter((n) => n.id !== node.id)
  links.value = links.value.filter(
    (l) => l.source_node_id !== node.id && l.target_node_id !== node.id,
  )
  if (selectedNodeId.value === node.id) {
    selectedNodeId.value = nodes.value[0]?.id ?? null
  }
}

async function searchDevices(keyword: string) {
  deviceLoading.value = true
  try {
    const data = await listDevices({ page_size: 50, keyword: keyword || undefined })
    deviceOptions.value = data.items || []
  } finally {
    deviceLoading.value = false
  }
}

function goToDevice(deviceId: string) {
  void router.push({ path: '/devices', query: { device_id: deviceId } })
}

async function handleSave() {
  if (!currentId.value) return
  nodes.value.forEach((node) => {
    if (node.port_layout) {
      node.port_layout.layout_locked = true
      syncLegacyFromPortLayout(node)
    }
  })
  syncLinksFromPortLayout(nodes.value, links.value)
  const ok = await saveCanvas()
  if (ok) {
    // 保存回写后再次锁定，避免后端未带回 layout_locked 时仍可改结构
    nodes.value.forEach((node) => {
      if (node.port_layout) node.port_layout.layout_locked = true
    })
    ElMessage.info('布局已锁定；可继续配置接口对端，修改布局请点击「编辑布局」')
  }
}

function startLayoutEdit() {
  const node = selectedNode.value
  if (!node?.port_layout || !canEdit.value) return
  node.port_layout.layout_locked = false
  ElMessage.info('已进入布局编辑：可调整面板结构；保存后将再次锁定')
}

const layoutLocked = computed(() => !!selectedNode.value?.port_layout?.layout_locked)
const canConfigPorts = computed(() => canEdit.value)
const canEditLayout = computed(() => canEdit.value && !layoutLocked.value)

watch(
  nodes,
  () => {
    if (selectedNodeId.value && !nodes.value.some((n) => n.id === selectedNodeId.value)) {
      selectedNodeId.value = nodes.value[0]?.id ?? null
    }
    if (!selectedNodeId.value && nodes.value.length) {
      selectNode(nodes.value[0])
    }
  },
  { deep: true },
)

onMounted(async () => {
  await loadTopologies()
  await searchDevices('')
  if (nodes.value.length && !selectedNodeId.value) {
    selectNode(nodes.value[0])
  }
})
</script>

<template>
  <div class="page" v-loading="loading">
    <el-card shadow="never" class="main-card">
      <section class="workspace">
        <div class="toolbar">
          <span class="title">设备定义</span>
          <el-button-group v-if="canEdit">
            <el-button :disabled="!currentId" @click="openCreate('switch')">网络设备</el-button>
            <el-button :disabled="!currentId" @click="openCreate('server')">服务器</el-button>
            <el-button :disabled="!currentId" @click="openCreate('security')">安全设备</el-button>
          </el-button-group>
          <el-button v-if="canEdit" type="primary" :loading="saving" :disabled="!currentId" @click="handleSave">
            保存
          </el-button>
        </div>

        <div v-if="currentId" class="content">
          <aside class="device-list">
            <div
              v-for="node in nodes"
              :key="node.id"
              class="device-item"
              :class="{ active: selectedNodeId === node.id }"
              @click="selectNode(node)"
            >
              <div class="name">{{ node.name }}</div>
              <div class="meta">
                {{ node.kind === 'switch' && node.port_layout?.switch_subtype
                  ? SWITCH_SUBTYPE_LABELS[node.port_layout.switch_subtype]
                  : NODE_KIND_LABELS[node.kind] }}
                · {{ node.port_layout?.height_u ?? 1 }}U
                · {{ node.port_layout?.ports?.length ?? 0 }} 接口
              </div>
              <div class="item-actions">
                <el-button
                  v-if="node.device_id"
                  type="primary"
                  link
                  size="small"
                  @click.stop="goToDevice(node.device_id!)"
                >
                  设备详情
                </el-button>
                <el-button
                  v-if="canEdit"
                  type="danger"
                  link
                  size="small"
                  @click.stop="removeNode(node)"
                >
                  删除
                </el-button>
              </div>
            </div>
            <el-empty v-if="!nodes.length" description="请添加设备" />
          </aside>

          <section v-if="selectedNode" class="editor-panel">
            <div class="panel-header">
              <el-input
                v-model="selectedNode.name"
                :disabled="!canEdit"
                style="width: 220px"
                placeholder="设备名称"
              />
              <el-select
                v-model="selectedNode.device_id"
                filterable
                remote
                clearable
                :remote-method="searchDevices"
                :loading="deviceLoading"
                placeholder="关联 DCIM 设备"
                :disabled="!canEdit"
                style="width: 280px"
              >
                <el-option
                  v-for="d in deviceOptions"
                  :key="d.id"
                  :label="`${d.hostname} (${d.serial_number})`"
                  :value="d.id"
                />
              </el-select>
              <el-tag v-if="layoutLocked" type="info" size="small">布局已锁定</el-tag>
              <el-tag v-else-if="canEdit" type="warning" size="small">布局编辑中</el-tag>
              <el-button
                v-if="canEdit && layoutLocked"
                type="primary"
                @click="startLayoutEdit"
              >
                编辑布局
              </el-button>
            </div>
            <p v-if="layoutLocked" class="mode-hint">
              布局已锁定，不可拖动/调整结构；单击选中接口，双击配置对端
            </p>
            <NetworkDeviceFrameEditor
              :key="selectedNode.id"
              :node="selectedNode"
              :peer-nodes="peerNodes"
              :editable="canConfigPorts"
              :layout-editable="canEditLayout"
            />
          </section>
          <el-empty v-else description="请选择设备以编辑接口构成" class="editor-empty" />
        </div>
        <el-empty v-else description="请先在「拓扑设计」中创建拓扑，或选择已有拓扑" />
      </section>
    </el-card>

    <el-dialog v-model="basicVisible" title="新建设备" width="620px">
      <el-form label-width="120px">
        <el-form-item label="类型">
          <el-tag>{{ NODE_KIND_LABELS[basicForm.kind] }}</el-tag>
        </el-form-item>
        <template v-if="basicForm.kind === 'switch'">
          <el-form-item label="设备类型" required>
            <el-select v-model="basicForm.switch_subtype" style="width: 100%" @change="onSwitchSubtypeChange">
              <el-option
                v-for="(label, key) in SWITCH_SUBTYPE_LABELS"
                :key="key"
                :label="label"
                :value="key"
              />
            </el-select>
          </el-form-item>

          <template v-if="isGigabitSwitch">
            <el-form-item label="电口数量">
              <el-input-number v-model="basicForm.main_port_count" :min="1" :max="128" />
            </el-form-item>
            <el-form-item label="上联光口数量">
              <el-input-number
                v-model="basicForm.uplink_port_count"
                :min="0"
                :max="8"
                @change="onCreateGigabitUplinkChange"
              />
              <div class="form-hint">最多 8 个；大于 4 时须为偶数（6/8），两排显示</div>
            </el-form-item>
            <el-form-item label="上联位置">
              <el-radio-group v-model="basicForm.uplink_position">
                <el-radio v-for="(label, key) in UPLINK_POSITION_LABELS" :key="key" :value="key">{{ label }}</el-radio>
              </el-radio-group>
            </el-form-item>
          </template>

          <template v-else-if="isTenGigabitSwitch">
            <el-form-item label="光口数量">
              <el-input-number v-model="basicForm.main_port_count" :min="1" :max="128" />
            </el-form-item>
            <el-form-item label="40/100G接口数量">
              <el-input-number
                v-model="basicForm.uplink_port_count"
                :min="0"
                :max="8"
                :step="2"
                @change="onCreateTenGigabitUplinkChange"
              />
              <div class="form-hint">须为偶数（2/4/6/8），两排向后扩展排列</div>
            </el-form-item>
            <el-form-item label="上联位置">
              <el-radio-group v-model="basicForm.uplink_position">
                <el-radio v-for="(label, key) in UPLINK_POSITION_LABELS" :key="key" :value="key">{{ label }}</el-radio>
              </el-radio-group>
            </el-form-item>
          </template>

          <template v-else-if="isCoreSwitch">
            <el-form-item label="板卡定义">
              <div class="card-list">
                <div v-for="(card, idx) in basicForm.line_cards" :key="card.id" class="card-row">
                  <span class="card-idx">板卡 {{ idx + 1 }}</span>
                  <el-select v-model="card.card_type" style="width: 140px" @change="onCreateLineCardTypeChange(card)">
                    <el-option
                      v-for="(label, key) in CORE_CARD_TYPE_LABELS"
                      :key="key"
                      :label="label"
                      :value="key as CoreCardType"
                    />
                  </el-select>
                  <span>接口数量</span>
                  <el-input-number
                    v-model="card.port_count"
                    :min="card.card_type === 'blank' ? 0 : 1"
                    :max="128"
                    :disabled="card.card_type === 'blank'"
                  />
                  <el-button
                    type="danger"
                    link
                    :disabled="basicForm.line_cards.length <= 1"
                    @click="removeLineCard(idx)"
                  >
                    删除
                  </el-button>
                </div>
                <el-button type="primary" link :disabled="basicForm.line_cards.length >= 16" @click="addLineCard">
                  + 添加板卡
                </el-button>
                <p class="card-hint">核心交换机按板卡定义接口，无独立上联口</p>
              </div>
            </el-form-item>
          </template>
        </template>
        <template v-else-if="isCreateServer">
          <el-form-item label="服务器规格" required>
            <el-radio-group v-model="basicForm.server_form_factor">
              <el-radio v-for="(label, key) in SERVER_FORM_FACTOR_LABELS" :key="key" :value="Number(key)">
                {{ label }}
              </el-radio>
            </el-radio-group>
            <div class="form-hint">
              1U 默认 2 张扩展卡；2U 参考背板左 3 / 中 3 / 右 2 共 8 槽。创建后可继续添加或删除网卡 / RAID / HBA。
            </div>
          </el-form-item>
        </template>
        <template v-else-if="isCreateSecurity">
          <el-form-item label="设备高度" required>
            <el-radio-group v-model="basicForm.security_height_u">
              <el-radio :value="1">1U</el-radio>
              <el-radio :value="2">2U</el-radio>
            </el-radio-group>
            <div class="form-hint">
              1U / 2U 机箱同宽；默认生成 WAN / LAN / HA / MGMT 接口区，创建后可调整位置与大小。
            </div>
          </el-form-item>
        </template>
        <el-form-item label="名称" required>
          <el-input v-model="basicForm.name" />
        </el-form-item>
        <el-form-item label="关联设备">
          <el-select
            v-model="basicForm.device_id"
            filterable
            remote
            clearable
            :remote-method="searchDevices"
            :loading="deviceLoading"
            style="width: 100%"
          >
            <el-option
              v-for="d in deviceOptions"
              :key="d.id"
              :label="`${d.hostname} (${d.serial_number})`"
              :value="d.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="basicVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmCreate">创建并编辑接口</el-button>
      </template>
    </el-dialog>
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
  padding: 16px;
}

.workspace {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}

.title {
  font-weight: 600;
}

.content {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.device-list {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 8px;
  overflow: auto;
}

.device-item {
  padding: 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 6px;
  border: 1px solid transparent;
}

.device-item:hover {
  background: #f5f7fa;
}

.device-item.active {
  background: #ecf5ff;
  border-color: #b3d8ff;
}

.device-item .name {
  font-weight: 500;
  font-size: 14px;
}

.device-item .meta {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.item-actions {
  margin-top: 6px;
}

.editor-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  min-height: 0;
}

.panel-header {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.mode-hint {
  margin: 0;
  font-size: 12px;
  color: #909399;
}

.editor-empty {
  grid-column: 2;
}

.card-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.card-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.card-idx {
  font-weight: 500;
  min-width: 56px;
}

.card-hint {
  margin: 0;
  color: #909399;
  font-size: 12px;
}

.form-hint {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
  line-height: 1.4;
}
</style>
