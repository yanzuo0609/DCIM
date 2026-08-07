<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NODE_KIND_LABELS,
  PORT_TYPE_LABELS,
  SWITCH_SUBTYPE_LABELS,
  listNodePortOptions,
  type NetworkLink,
  type NetworkNode,
  type SwitchSubtype,
} from '@/api/network'
import { FABRIC_ROLE_OPTIONS, type FabricRole } from '@/utils/wiringTypes'
import { resolveNodeFabricRole } from '@/utils/fabricRole'

const props = defineProps<{
  node: NetworkNode
  nodes: NetworkNode[]
  links: NetworkLink[]
  editable?: boolean
  /** 拓扑内可选设备组 */
  groupOptions?: string[]
}>()

const emit = defineEmits<{
  connectPort: [portId: string]
  clearPort: [portId: string]
  rename: [name: string]
  updateMeta: [patch: { network_role?: string | null; device_group?: string | null }]
  manageGroups: []
  unplace: []
  remove: []
  goDevice: [deviceId: string]
}>()

const editingName = ref(false)
const nameDraft = ref('')
const roleDraft = ref<FabricRole | ''>('')
const groupDraft = ref('')

watch(
  () => props.node.id,
  () => {
    roleDraft.value = (props.node.network_role as FabricRole) || resolveNodeFabricRole(props.node)
    groupDraft.value = props.node.device_group || ''
  },
  { immediate: true },
)

const kindLabel = computed(() => {
  const n = props.node
  if (n.kind === 'switch' && n.port_layout?.switch_subtype) {
    return SWITCH_SUBTYPE_LABELS[n.port_layout.switch_subtype as SwitchSubtype]
  }
  return NODE_KIND_LABELS[n.kind]
})

const effectiveRole = computed(() => resolveNodeFabricRole(props.node))

const portRows = computed(() => {
  const opts = listNodePortOptions(props.node)
  return opts.map((opt) => {
    const frame = props.node.port_layout?.ports?.find((p) => p.id === opt.id)
    const link =
      props.links.find(
        (l) =>
          (l.source_node_id === props.node.id && l.source_port === opt.id) ||
          (l.target_node_id === props.node.id && l.target_port === opt.id),
      ) || null
    let peerNodeId = frame?.peer_node_id || null
    let peerPort = frame?.peer_port || null
    let peerLabel = frame?.peer_label || null
    if (link) {
      if (link.source_node_id === props.node.id) {
        peerNodeId = link.target_node_id
        peerPort = link.target_port
        peerLabel = link.label
      } else {
        peerNodeId = link.source_node_id
        peerPort = link.source_port
        peerLabel = link.label
      }
    }
    const peerNode = peerNodeId ? props.nodes.find((n) => n.id === peerNodeId) : null
    return {
      id: opt.id,
      label: opt.label,
      portType: opt.port_type,
      purpose: frame?.purpose || null,
      linked: !!(peerNodeId && peerPort),
      peerNodeId,
      peerPort,
      peerName: peerNode?.name || peerLabel || peerNodeId?.slice(0, 8) || '',
      linkLabel: peerLabel,
    }
  })
})

const linkedCount = computed(() => portRows.value.filter((p) => p.linked).length)

function startRename() {
  nameDraft.value = props.node.name
  editingName.value = true
}

function commitRename() {
  const name = nameDraft.value.trim()
  if (name && name !== props.node.name) emit('rename', name)
  editingName.value = false
}

function commitRole() {
  emit('updateMeta', { network_role: roleDraft.value || null })
}

function commitGroup() {
  const raw = typeof groupDraft.value === 'string' ? groupDraft.value.trim() : ''
  groupDraft.value = raw
  emit('updateMeta', { device_group: raw || null })
}

function peerTitle(row: (typeof portRows.value)[0]) {
  if (!row.linked) return '未连线'
  return `${row.peerName} · ${row.peerPort}`
}
</script>

<template>
  <div class="inspector-panel">
    <h3>设备详情</h3>

    <div class="field">
      <span class="label">名称</span>
      <div v-if="editable && editingName" class="name-edit">
        <el-input v-model="nameDraft" size="small" @keyup.enter="commitRename" @blur="commitRename" />
      </div>
      <div v-else class="name-row">
        <strong>{{ node.name }}</strong>
        <el-button v-if="editable" link type="primary" size="small" @click="startRename">改名</el-button>
      </div>
    </div>

    <p><span class="label">类型</span>{{ kindLabel }}</p>
    <div class="field">
      <span class="label">角色</span>
      <el-select
        v-if="editable"
        v-model="roleDraft"
        size="small"
        style="width: 140px"
        @change="commitRole"
      >
        <el-option
          v-for="o in FABRIC_ROLE_OPTIONS"
          :key="o.value"
          :label="o.label"
          :value="o.value"
        />
      </el-select>
      <span v-else>{{ effectiveRole }}</span>
    </div>
    <div class="field">
      <span class="label">设备组</span>
      <div v-if="editable" class="group-edit">
        <el-select
          v-model="groupDraft"
          size="small"
          clearable
          filterable
          allow-create
          default-first-option
          placeholder="选择或新建"
          style="width: 140px"
          @change="commitGroup"
        >
          <el-option v-for="g in groupOptions || []" :key="g" :label="g" :value="g" />
        </el-select>
        <el-button type="primary" link size="small" @click="emit('manageGroups')">管理</el-button>
      </div>
      <span v-else>{{ node.device_group || '-' }}</span>
    </div>
    <p>
      <span class="label">状态</span>
      {{ node.on_canvas === false ? '待放置 / 可作模板' : '已放置' }}
    </p>
    <p v-if="node.on_canvas !== false">
      <span class="label">坐标</span>{{ Math.round(node.pos_x) }}, {{ Math.round(node.pos_y) }}
    </p>
    <p>
      <span class="label">接口</span>{{ linkedCount }} / {{ portRows.length }} 已连线
    </p>

    <template v-if="node.device">
      <p><span class="label">主机名</span>{{ node.device.hostname }}</p>
      <p>
        <span class="label">位置</span>{{ node.device.room_name || '-' }} /
        {{ node.device.rack_code || '-' }} U{{ node.device.u_position ?? '-' }}
      </p>
      <el-button type="primary" link @click="emit('goDevice', node.device!.device_id)">
        查看台账设备 →
      </el-button>
    </template>

    <h4 class="sub">接口与连线</h4>
    <div v-if="!portRows.length" class="empty">暂无接口定义，请先在「设备定义」配置面板</div>
    <div v-else class="port-list">
      <div v-for="row in portRows" :key="row.id" class="port-row" :class="{ linked: row.linked }">
        <div class="port-main">
          <div class="port-id">{{ row.id }}</div>
          <div class="port-meta">
            {{ PORT_TYPE_LABELS[row.portType] || row.portType }}
            <span v-if="row.purpose"> · {{ row.purpose }}</span>
            <span v-if="row.label && row.label !== row.id"> · {{ row.label }}</span>
          </div>
          <div class="peer" :class="{ free: !row.linked }">
            {{ peerTitle(row) }}
          </div>
        </div>
        <div v-if="editable" class="port-actions">
          <el-button
            v-if="!row.linked"
            type="primary"
            link
            size="small"
            @click="emit('connectPort', row.id)"
          >
            连接
          </el-button>
          <el-button v-else type="danger" link size="small" @click="emit('clearPort', row.id)">
            断开
          </el-button>
        </div>
      </div>
    </div>

    <div v-if="editable" class="danger-actions">
      <el-button
        v-if="node.on_canvas !== false"
        type="warning"
        plain
        size="small"
        @click="emit('unplace')"
      >
        移回待放置
      </el-button>
      <el-button type="danger" plain size="small" @click="emit('remove')">删除设备</el-button>
    </div>
  </div>
</template>

<style scoped>
.inspector-panel h3 {
  margin: 0 0 12px;
  font-size: 15px;
}

.sub {
  margin: 14px 0 8px;
  font-size: 13px;
  color: #606266;
}

.field {
  margin-bottom: 8px;
}

.label {
  display: inline-block;
  min-width: 48px;
  color: #909399;
  font-size: 12px;
  margin-right: 6px;
}

.name-row {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.name-edit {
  display: inline-block;
  width: 160px;
}

.group-edit {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

p {
  margin: 0 0 8px;
  font-size: 13px;
}

.empty {
  font-size: 12px;
  color: #c0c4cc;
}

.port-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: calc(100vh - 420px);
  overflow: auto;
}

.port-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 6px;
  padding: 8px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fafafa;
}

.port-row.linked {
  background: #f0f9eb;
  border-color: #e1f3d8;
}

.port-id {
  font-size: 12px;
  font-weight: 600;
  color: #303133;
}

.port-meta {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}

.peer {
  font-size: 12px;
  color: #67c23a;
  margin-top: 4px;
}

.peer.free {
  color: #e6a23c;
}

.port-actions {
  flex-shrink: 0;
}

.danger-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}
</style>
