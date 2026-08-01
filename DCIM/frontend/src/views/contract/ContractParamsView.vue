<script setup lang="ts">
import DeviceParamProfilesPanel from '@/components/DeviceParamProfilesPanel.vue'
</script>

<template>
  <div class="params-page">
    <header class="page-head">
      <div>
        <h2>设备参数</h2>
        <p>配置 CPU / 内存 / 磁盘 / RAID 等设备参数档案，供设备台账关联使用</p>
      </div>
    </header>
    <el-card shadow="never" class="params-card">
      <DeviceParamProfilesPanel />
    </el-card>
  </div>
</template>

<style scoped>
.params-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.page-head h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #1f2a37;
}

.page-head p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #6b7c8f;
}

.params-card {
  border: 1px solid #e8eef5;
}
</style>
