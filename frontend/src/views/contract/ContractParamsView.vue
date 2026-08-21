<script setup lang="ts">
import DeviceParamProfilesPanel from '@/components/DeviceParamProfilesPanel.vue'
</script>

<template>
  <div class="params-page">
    <header class="page-head">
      <div>
        <h2>资产详细参数</h2>
        <p>
          按设备名称关联采购汇总；配置参数统一展示于一列，完善后可供资源统计与设备台账关联
        </p>
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
