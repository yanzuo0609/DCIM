<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const tabs = computed(() => {
  const items: Array<{ path: string; label: string; permission?: string }> = [
    { path: '/racks/templates', label: '机柜模板管理', permission: 'rack:view' },
  ]
  return items.filter((item) => !item.permission || auth.hasPermission(item.permission))
})

const activeTab = computed(() => route.path)

function onTabClick(path: string) {
  if (route.path !== path) {
    void router.push(path)
  }
}
</script>

<template>
  <div class="rack-section">
    <nav v-if="tabs.length > 1" class="rack-tabs" aria-label="机柜模板管理导航">
      <button
        v-for="tab in tabs"
        :key="tab.path"
        type="button"
        class="rack-tab"
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
.rack-section {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-height: 100%;
}

.rack-tabs {
  display: flex;
  align-items: center;
  gap: 0;
  margin: -4px 0 16px;
  padding: 0;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  overflow: hidden;
  width: fit-content;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.rack-tab {
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

.rack-tab:last-child {
  border-right: none;
}

.rack-tab:hover {
  color: #409eff;
  background: #f5f9ff;
}

.rack-tab.active {
  color: #409eff;
  background: #ecf5ff;
}
</style>
