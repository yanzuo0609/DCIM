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
    { path: '/devices/personnel', label: '组织架构图', exact: true },
    { path: '/devices/personnel/internals', label: '用户相关方', exact: false },
    { path: '/devices/personnel/suppliers', label: '供应商相关方', exact: false },
  ]
})

function isActive(tab: { path: string; exact: boolean }) {
  if (tab.exact) {
    return route.path === '/devices/personnel' || route.path === '/devices/personnel/'
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
  <div class="personnel-section">
    <nav v-if="tabs.length" class="personnel-tabs" aria-label="人员管理导航">
      <button
        v-for="tab in tabs"
        :key="tab.path"
        type="button"
        class="personnel-tab"
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
.personnel-section {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-height: 100%;
  height: 100%;
}

.personnel-tabs {
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

.personnel-tab {
  margin: 0;
  padding: 10px 22px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  color: #606266;
  border-right: 1px solid #ebeef5;
}

.personnel-tab:last-child {
  border-right: none;
}

.personnel-tab:hover {
  color: #409eff;
  background: #f5f9ff;
}

.personnel-tab.active {
  color: #409eff;
  font-weight: 600;
  background: #ecf5ff;
}
</style>
