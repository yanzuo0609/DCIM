<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useScreenStore } from '@/stores/screen'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const screen = useScreenStore()

const activeMenu = computed(() => {
  if (route.path.startsWith('/racks')) {
    if (route.path.startsWith('/racks/templates')) return '/racks/templates'
    return '/racks/templates'
  }
  if (route.path.startsWith('/warehouses')) return '/warehouses'
  if (route.path.startsWith('/rooms') || route.path.startsWith('/datacenters')) {
    if (route.path.startsWith('/rooms/simulate')) return '/rooms/simulate'
    if (route.path.startsWith('/rooms/manage')) return '/rooms/manage'
    if (route.path.startsWith('/datacenters')) return '/datacenters'
    return '/rooms/manage'
  }
  if (route.path.startsWith('/network')) return route.path
  // 合同子页（汇总/参数）仍高亮「合同信息」菜单
  if (route.path.startsWith('/devices/contracts')) return '/devices/contracts'
  if (route.path.startsWith('/devices/personnel')) return '/devices/personnel'
  if (route.path.startsWith('/system')) return route.path
  return route.path
})
const openedMenus = computed(() => {
  const menus: string[] = []
  if (route.path.startsWith('/devices')) menus.push('device-menu')
  if (route.path.startsWith('/network')) menus.push('network-menu')
  if (route.path.startsWith('/system')) menus.push('/system')
  if (
    route.path.startsWith('/rooms') ||
    route.path.startsWith('/datacenters') ||
    route.path.startsWith('/racks') ||
    route.path.startsWith('/warehouses')
  ) {
    menus.push('datacenter-menu')
  }
  return menus
})
const displayName = computed(() => auth.profile?.full_name || auth.profile?.username || 'User')
const canManageSystem = computed(
  () =>
    auth.hasPermission('user:view') ||
    auth.hasPermission('role:view') ||
    auth.hasPermission('audit:view'),
)
const canManageScreen = computed(
  () => canManageSystem.value || auth.hasPermission('dashboard:view'),
)

function handleMenuSelect(index: string) {
  // 主菜单「中心机房管理」始终进入全部机房（清除 datacenter_id 筛选）
  if (index === '/rooms/manage') {
    void router.push({ path: '/rooms/manage', query: {} })
    return
  }
  if (route.path !== index) {
    void router.push(index)
  }
}

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <el-container class="layout">
    <el-aside width="220px" class="sidebar">
      <div class="brand">
        <h1>RackDCIM Pro</h1>
        <p>AI Native DCIM</p>
      </div>
      <el-menu
        :key="activeMenu"
        :default-active="activeMenu"
        :default-openeds="openedMenus"
        background-color="#1d1e2c"
        text-color="#fff"
        @select="handleMenuSelect"
      >
        <el-menu-item index="/">
          <span>Dashboard</span>
        </el-menu-item>
        <el-menu-item v-if="screen.menuEnabled" index="/dashboard/screen">
          <span>运营大屏</span>
        </el-menu-item>
        <el-sub-menu
          v-if="auth.hasPermission('datacenter:view') || auth.hasPermission('rack:view')"
          index="datacenter-menu"
        >
          <template #title><span>数据中心</span></template>
          <el-menu-item v-if="auth.hasPermission('datacenter:view')" index="/datacenters">
            数据中心管理
          </el-menu-item>
          <el-menu-item v-if="auth.hasPermission('datacenter:view')" index="/rooms/manage">
            中心机房管理
          </el-menu-item>
          <el-menu-item
            v-if="auth.hasPermission('datacenter:view') || auth.hasPermission('rack:view')"
            index="/rooms/simulate"
          >
            机房3D仿真
          </el-menu-item>
          <el-menu-item v-if="auth.hasPermission('rack:view')" index="/racks/templates">
            机柜模板管理
          </el-menu-item>
          <el-menu-item v-if="auth.hasPermission('datacenter:view')" index="/warehouses">
            中心库房管理
          </el-menu-item>
        </el-sub-menu>
        <el-sub-menu v-if="auth.hasPermission('network:view')" index="network-menu">
          <template #title><span>网络设计</span></template>
          <el-menu-item index="/network/models">模型库</el-menu-item>
          <el-menu-item index="/network/topology">拓扑管理</el-menu-item>
          <el-menu-item index="/network/interfaces">接口设计</el-menu-item>
        </el-sub-menu>
        <el-sub-menu v-if="auth.hasPermission('device:view')" index="device-menu">
          <template #title><span>资源管理</span></template>
          <el-menu-item index="/devices">设备管理</el-menu-item>
          <el-menu-item index="/devices/contracts">合同信息</el-menu-item>
          <el-menu-item index="/devices/personnel">人员管理</el-menu-item>
        </el-sub-menu>
        <el-sub-menu
          v-if="canManageSystem || canManageScreen"
          index="/system"
        >
          <template #title><span>系统管理</span></template>
          <el-menu-item v-if="auth.hasPermission('user:view')" index="/system/users">用户管理</el-menu-item>
          <el-menu-item v-if="auth.hasPermission('role:view')" index="/system/roles">角色管理</el-menu-item>
          <el-menu-item v-if="auth.hasPermission('audit:view')" index="/system/audit">日志管理</el-menu-item>
          <el-menu-item v-if="canManageScreen" index="/system/screen">大屏管理</el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span>数据中心基础设施管理平台</span>
        <div class="header-actions">
          <span class="username">{{ displayName }}</span>
          <el-button type="primary" link @click="handleLogout">退出</el-button>
        </div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  min-height: 100vh;
}

.sidebar {
  background: #1d1e2c;
  color: #fff;
}

.brand {
  padding: 24px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.brand h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.brand p {
  margin: 6px 0 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  font-weight: 500;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.username {
  color: #606266;
  font-size: 14px;
}

.main {
  background: #f5f7fa;
}
</style>
