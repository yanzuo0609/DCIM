<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const tabs = computed(() => {
  const items = [
    { path: '/network/models', label: '模型库' },
    { path: '/network/topology', label: '拓扑管理' },
    { path: '/network/interfaces', label: '接口设计' },
  ]
  return auth.hasPermission('network:view') ? items : []
})

const activeTab = computed(() => route.path)

function onTabClick(path: string) {
  if (route.path !== path) {
    void router.push({ path, query: route.query })
  }
}
</script>

<template>
  <div class="network-section">
    <nav v-if="tabs.length > 1" class="network-tabs" aria-label="网络设计导航">
      <button
        v-for="tab in tabs"
        :key="tab.path"
        type="button"
        class="network-tab"
        :class="{ active: activeTab === tab.path || activeTab.startsWith(`${tab.path}/`) }"
        @click="onTabClick(tab.path)"
      >
        {{ tab.label }}
      </button>
    </nav>
    <router-view />
  </div>
</template>

<style scoped>
.network-section {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-height: 100%;
}

.network-tabs {
  display: flex;
  align-items: center;
  margin: -4px 0 16px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  overflow: hidden;
  width: fit-content;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.network-tab {
  margin: 0;
  padding: 10px 20px;
  border: none;
  border-right: 1px solid #ebeef5;
  background: #fff;
  color: #606266;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;
}

.network-tab:last-child {
  border-right: none;
}

.network-tab:hover {
  color: #409eff;
  background: #f5f9ff;
}

.network-tab.active {
  color: #409eff;
  background: #ecf5ff;
}
</style>
