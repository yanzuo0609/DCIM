<script setup lang="ts">
withDefaults(
  defineProps<{
    /** 弹层标题 */
    title?: string
    /** 说明正文 */
    content: string
    width?: number | string
  }>(),
  {
    title: '说明',
    width: 320,
  },
)
</script>

<template>
  <el-popover
    v-if="content && content !== '—'"
    placement="top-start"
    :width="width"
    trigger="click"
    teleported
  >
    <template #reference>
      <button type="button" class="title-hint-bang" :title="title" :aria-label="title">!</button>
    </template>
    <div class="title-hint-body">
      <div class="title-hint-title">{{ title }}</div>
      <div class="title-hint-text">{{ content }}</div>
    </div>
  </el-popover>
</template>

<style scoped>
.title-hint-bang {
  position: absolute;
  top: -4px;
  right: -2px;
  width: 14px;
  height: 14px;
  margin: 0;
  padding: 0;
  border: 1px solid #e6a23c;
  border-radius: 50%;
  background: #fdf6ec;
  color: #e6a23c;
  font-size: 10px;
  font-weight: 700;
  line-height: 12px;
  text-align: center;
  cursor: pointer;
  flex: 0 0 auto;
  z-index: 1;
}
.title-hint-bang:hover {
  background: #e6a23c;
  color: #fff;
}
.title-hint-body {
  font-size: 12px;
  line-height: 1.5;
  color: #606266;
}
.title-hint-title {
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}
.title-hint-text {
  word-break: break-word;
  white-space: pre-wrap;
}
</style>
