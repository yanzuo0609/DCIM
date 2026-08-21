<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

type TabItem = {
  path: string
  label: string
  exact?: boolean
  match?: (path: string) => boolean
}

const tabs = computed<TabItem[]>(() => {
  if (!auth.hasPermission('device:view')) return []
  return [
    { path: '/devices/contracts', label: '合同台账', exact: true },
    {
      path: '/devices/contracts/summary',
      label: '资产汇总',
      match: (path) =>
        path === '/devices/contracts/summary' ||
        path.startsWith('/devices/contracts/summary/') ||
        path === '/devices/contracts/details' ||
        path.startsWith('/devices/contracts/details/'),
    },
    { path: '/devices/contracts/params', label: '资产详细参数', exact: false },
  ]
})

const summarySubTabs = computed(() => [
  { path: '/devices/contracts/summary', label: '按设备类型', exact: true },
  { path: '/devices/contracts/details', label: '按合同', exact: false },
])

const showSummarySubTabs = computed(() => {
  const path = route.path
  return (
    path === '/devices/contracts/summary' ||
    path.startsWith('/devices/contracts/summary/') ||
    path === '/devices/contracts/details' ||
    path.startsWith('/devices/contracts/details/')
  )
})

function isActive(tab: TabItem) {
  if (tab.match) return tab.match(route.path)
  if (tab.exact) {
    return route.path === tab.path || route.path === `${tab.path}/`
  }
  return route.path === tab.path || route.path.startsWith(`${tab.path}/`)
}

function isSubActive(tab: { path: string; exact: boolean }) {
  if (tab.exact) {
    return route.path === tab.path || route.path === `${tab.path}/`
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

    <nav
      v-if="showSummarySubTabs"
      class="contract-subtabs"
      aria-label="资产汇总子菜单"
    >
      <button
        v-for="tab in summarySubTabs"
        :key="tab.path"
        type="button"
        class="contract-subtab"
        :class="{ active: isSubActive(tab) }"
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
  margin: -4px 0 10px;
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

.contract-subtabs {
  display: flex;
  align-items: center;
  margin: 0 0 14px;
  gap: 4px;
  width: fit-content;
}

.contract-subtab {
  margin: 0;
  padding: 6px 14px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  background: #fff;
  color: #606266;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease, border-color 0.15s ease;
}

.contract-subtab:hover {
  color: #409eff;
  border-color: #c6e2ff;
  background: #f5f9ff;
}

.contract-subtab.active {
  color: #409eff;
  border-color: #409eff;
  background: #ecf5ff;
  font-weight: 600;
}
</style>
