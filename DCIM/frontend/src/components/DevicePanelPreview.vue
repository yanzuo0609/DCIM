<script setup lang="ts">
import { computed } from 'vue'
import NetworkDeviceFrameEditor from '@/components/NetworkDeviceFrameEditor.vue'
import type { NetworkNode, NetworkNodeKind, PortLayout } from '@/api/network'

const props = defineProps<{
  portLayout: PortLayout | Record<string, unknown> | null | undefined
  networkKind?: string | null
  deviceName?: string | null
}>()

const previewNode = computed<NetworkNode | null>(() => {
  if (!props.portLayout) return null
  const kind = (props.networkKind || 'switch') as NetworkNodeKind
  const layout = props.portLayout as PortLayout
  return {
    id: 'device-panel-preview',
    topology_id: '',
    kind: kind === 'server' || kind === 'security' ? kind : 'switch',
    name: props.deviceName || '设备面板',
    device_id: null,
    pos_x: 0,
    pos_y: 0,
    switch_port_count: layout.ports?.length || 1,
    slots: null,
    port_layout: { ...layout, layout_locked: true },
    on_canvas: false,
    device: null,
  }
})
</script>

<template>
  <div v-if="previewNode" class="panel-preview">
    <div class="preview-title">设备定义面板</div>
    <NetworkDeviceFrameEditor :node="previewNode" :peer-nodes="[]" :editable="false" />
  </div>
  <el-empty v-else description="尚未关联设备定义面板" :image-size="64" />
</template>

<style scoped>
.panel-preview {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 8px;
  background: #fafafa;
  overflow: auto;
  max-height: 420px;
}

.preview-title {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
}
</style>
