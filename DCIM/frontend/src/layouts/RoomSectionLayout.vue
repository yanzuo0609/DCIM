<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const tabs = computed(() => {
  const items: Array<{ path: string; label: string; permission?: string }> = [
    { path: '/datacenters', label: '数据中心', permission: 'datacenter:view' },
    { path: '/rooms/manage', label: '机房管理', permission: 'datacenter:view' },
    { path: '/rooms/simulate', label: '3D 仿真', permission: 'datacenter:view' },
    { path: '/rooms/templates', label: '机柜模板', permission: 'rack:view' },
  ]
  return items.filter((item) => {
    if (!item.permission) return true
    if (item.path === '/rooms/simulate') {
      return auth.hasPermission('datacenter:view') || auth.hasPermission('rack:view')
    }
    return auth.hasPermission(item.permission)
  })
})

const activeTab = computed(() => route.path)

function onTabClick(path: string) {
  // 「机房管理」Tab：显示全部机房；其它入口同样清除无关筛选
  if (path === '/rooms/manage') {
    void router.push({ path: '/rooms/manage', query: {} })
    return
  }
  if (route.path !== path) {
    void router.push(path)
  }
}
</script>

<template>
  <div class="room-section">
    <nav v-if="tabs.length > 1" class="room-tabs" aria-label="数据中心导航">
      <button
        v-for="tab in tabs"
        :key="tab.path"
        type="button"
        class="room-tab"
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
.room-section {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-height: 100%;
}

.room-tabs {
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

.room-tab {
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

.room-tab:last-child {
  border-right: none;
}

.room-tab:hover {
  color: #409eff;
  background: #f5f9ff;
}

.room-tab.active {
  color: #409eff;
  background: #ecf5ff;
}
</style>
