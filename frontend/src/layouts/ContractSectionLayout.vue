<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const tabs = computed(() => {
  if (!auth.hasPermission('device:view')) return []
  return [
    { path: '/devices/contracts', label: '合同台账', exact: true },
    { path: '/devices/contracts/summary', label: '采购汇总', exact: false },
    { path: '/devices/contracts/params', label: '设备参数', exact: false },
  ]
})

function isActive(tab: { path: string; exact: boolean }) {
  if (tab.exact) {
    return route.path === '/devices/contracts' || route.path === '/devices/contracts/'
  }
  return route.path === tab.path || route.path.startsWith(`${tab.path}/`)
}

function onTabClick(path: string) {
  if (route.path !== path) {
    void router.push(path)
  }
}
</script>

<template>
  <div class="contract-section">
    <nav v-if="tabs.length" class="contract-tabs" aria-label="合同信息导航">
      <button
        v-for="tab in tabs"
        :key="tab.path"
        type="button"
        class="contract-tab"
        :class="{ active: isActive(tab) }"
        @click="onTabClick(tab.path)"
      >
        {{ tab.label }}
      </button>
    </nav>
    <router-view />
  </div>
</template>

<style scoped>
.contract-section {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-height: 100%;
  height: 100%;
}

.contract-section > :deep(.summary-page) {
  flex: 1;
  min-height: 0;
}

.contract-tabs {
  display: flex;
  align-items: center;
  margin: -4px 0 14px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  overflow: hidden;
  width: fit-content;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.contract-tab {
  margin: 0;
  padding: 10px 22px;
  border: none;
  border-right: 1px solid #ebeef5;
  background: #fff;
  color: #606266;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;
}

.contract-tab:last-child {
  border-right: none;
}

.contract-tab:hover {
  color: #409eff;
  background: #f5f9ff;
}

.contract-tab.active {
  color: #409eff;
  background: #ecf5ff;
}
</style>
