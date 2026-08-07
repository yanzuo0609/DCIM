<script setup lang="ts">
import { computed } from 'vue'
import TopologyDeviceIcon from '@/components/TopologyDeviceIcon.vue'
import type { NetworkDesignModel } from '@/api/networkModelDesign'
import { designModelIconProps } from '@/utils/designModelIcon'

const props = defineProps<{
  rootFolderId: string | null
  models: NetworkDesignModel[]
  selectedModelId: string | null
  disabled?: boolean
  hideTitle?: boolean
  loading?: boolean
}>()

const emit = defineEmits<{
  select: [modelId: string]
}>()

/** 预计算图标参数，避免列表每次渲染重复推导 */
const modelRows = computed(() =>
  props.models.map((m) => ({
    model: m,
    icon: designModelIconProps(m),
  })),
)
</script>

<template>
  <div class="model-library" v-loading="loading">
    <div v-if="!hideTitle" class="side-title">
      模型库
      <span v-if="rootFolderId" class="count">{{ models.length }}</span>
    </div>
    <div v-else-if="rootFolderId" class="count-row">
      <span class="count">{{ models.length }} 个模型</span>
    </div>
    <template v-if="!rootFolderId">
      <el-empty description="请先选择项目或文件夹" :image-size="56" />
    </template>
    <template v-else-if="!models.length && !loading">
      <div class="empty-hint">该目录下暂无模型</div>
    </template>
    <div v-else class="model-list">
      <button
        v-for="row in modelRows"
        :key="row.model.id"
        type="button"
        class="model-card"
        :class="{ active: selectedModelId === row.model.id }"
        :disabled="disabled"
        @click="emit('select', row.model.id)"
      >
        <TopologyDeviceIcon v-bind="row.icon" :size="36" />
        <div class="meta">
          <span class="name">
            {{ row.model.name }}
            <span v-if="!row.model.is_published" class="draft">未发布</span>
          </span>
          <span class="sub">{{ row.model.category }}/{{ row.model.subtype }}</span>
        </div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.model-library {
  margin-top: 4px;
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.side-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.count-row {
  margin-bottom: 6px;
}
.count {
  font-size: 11px;
  font-weight: 500;
  color: #909399;
  background: #f0f2f5;
  border-radius: 10px;
  padding: 0 6px;
  line-height: 18px;
}
.empty-hint {
  font-size: 12px;
  color: #909399;
  padding: 8px 0;
}
.model-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  max-height: min(560px, 62vh);
  overflow: auto;
}
.model-card {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 8px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  text-align: left;
}
.model-card:hover:not(:disabled) {
  border-color: #409eff;
  background: #f5faff;
}
.model-card.active {
  border-color: #409eff;
  background: #ecf5ff;
  box-shadow: inset 0 0 0 1px #409eff;
}
.model-card:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 2px;
}
.name {
  font-size: 12px;
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 4px;
}
.draft {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 500;
  color: #e6a23c;
  background: #fdf6ec;
  border-radius: 2px;
  padding: 0 4px;
  line-height: 16px;
}
.sub {
  font-size: 11px;
  color: #909399;
}
</style>
