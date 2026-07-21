<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeMenu = computed(() => route.path)
const openedMenus = computed(() =>
  route.path.startsWith('/devices') ? ['device-menu'] : [],
)
const displayName = computed(() => auth.profile?.full_name || auth.profile?.username || 'User')

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
        :default-active="activeMenu"
        :default-openeds="openedMenus"
        router
        background-color="#1d1e2c"
        text-color="#fff"
      >
        <el-menu-item index="/">
          <span>Dashboard</span>
        </el-menu-item>
        <el-menu-item v-if="auth.hasPermission('datacenter:view')" index="/datacenters">
          <span>数据中心</span>
        </el-menu-item>
        <el-menu-item v-if="auth.hasPermission('datacenter:view')" index="/rooms">
          <span>机房</span>
        </el-menu-item>
        <el-menu-item v-if="auth.hasPermission('rack:view')" index="/racks">
          <span>机柜</span>
        </el-menu-item>
        <el-sub-menu v-if="auth.hasPermission('device:view')" index="device-menu">
          <template #title><span>设备</span></template>
          <el-menu-item index="/devices">设备管理</el-menu-item>
          <el-menu-item index="/devices/contracts">合同信息</el-menu-item>
        </el-sub-menu>
        <el-sub-menu v-if="auth.hasPermission('user:view') || auth.hasPermission('role:view')" index="/system">
          <template #title><span>系统管理</span></template>
          <el-menu-item v-if="auth.hasPermission('user:view')" index="/system/users">用户管理</el-menu-item>
          <el-menu-item v-if="auth.hasPermission('role:view')" index="/system/roles">角色管理</el-menu-item>
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
