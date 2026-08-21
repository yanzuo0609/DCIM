import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useScreenStore } from '@/stores/screen'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/dashboard/screen',
      name: 'dashboard-screen',
      component: () => import('@/views/DashboardScreenView.vue'),
      meta: { fullscreen: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
        },
        {
          path: 'datacenters',
          component: () => import('@/layouts/RoomSectionLayout.vue'),
          meta: { permission: 'datacenter:view' },
          children: [
            {
              path: '',
              name: 'datacenters',
              component: () => import('@/views/DatacenterView.vue'),
              meta: { permission: 'datacenter:view' },
            },
          ],
        },
        {
          path: 'rooms',
          component: () => import('@/layouts/RoomSectionLayout.vue'),
          children: [
            {
              path: '',
              redirect: '/rooms/manage',
            },
            {
              path: 'simulate',
              name: 'rooms-simulate',
              component: () => import('@/views/Room3DSimulateView.vue'),
              meta: { permission: 'datacenter:view' },
            },
            {
              path: 'manage',
              name: 'rooms-manage',
              component: () => import('@/views/RoomView.vue'),
              meta: { permission: 'datacenter:view' },
            },
            {
              path: 'templates',
              redirect: '/racks/templates',
            },
          ],
        },
        {
          path: 'racks',
          component: () => import('@/layouts/RackSectionLayout.vue'),
          children: [
            {
              path: '',
              redirect: '/racks/templates',
            },
            {
              path: 'templates',
              name: 'rack-templates',
              component: () => import('@/views/RackView.vue'),
              meta: { permission: 'rack:view' },
            },
          ],
        },
        {
          path: 'warehouses',
          name: 'warehouses',
          component: () => import('@/views/WarehouseView.vue'),
          meta: { permission: 'datacenter:view' },
        },
        {
          path: 'warehouses/:id/assets',
          name: 'warehouse-assets',
          component: () => import('@/views/WarehouseAssetView.vue'),
          meta: { permission: 'datacenter:view' },
        },
        {
          path: 'devices',
          name: 'devices',
          component: () => import('@/views/DeviceView.vue'),
          meta: { permission: 'device:view' },
        },
        {
          path: 'devices/contracts',
          component: () => import('@/layouts/ContractSectionLayout.vue'),
          meta: { permission: 'device:view' },
          children: [
            {
              path: '',
              name: 'device-contracts',
              component: () => import('@/views/ContractView.vue'),
              meta: { permission: 'device:view' },
            },
            {
              path: 'summary',
              name: 'device-contracts-summary',
              component: () => import('@/views/contract/ContractSummaryView.vue'),
              meta: { permission: 'device:view' },
            },
            {
              path: 'params',
              name: 'device-contracts-params',
              component: () => import('@/views/contract/ContractParamsView.vue'),
              meta: { permission: 'device:view' },
            },
          ],
        },
        {
          path: 'devices/personnel',
          component: () => import('@/layouts/PersonnelSectionLayout.vue'),
          meta: { permission: 'device:view' },
          children: [
            {
              path: '',
              name: 'device-personnel-org',
              component: () => import('@/views/personnel/PersonnelOrgDesignView.vue'),
              meta: { permission: 'device:view' },
            },
            {
              path: 'internals',
              name: 'device-personnel-internals',
              component: () => import('@/views/personnel/PersonnelInternalView.vue'),
              meta: { permission: 'device:view' },
            },
            {
              path: 'suppliers',
              name: 'device-personnel-suppliers',
              component: () => import('@/views/personnel/PersonnelSupplierView.vue'),
              meta: { permission: 'device:view' },
            },
          ],
        },
        {
          path: 'network',
          component: () => import('@/layouts/NetworkSectionLayout.vue'),
          meta: { permission: 'network:view' },
          children: [
            {
              path: '',
              redirect: '/network/models',
            },
            {
              path: 'models',
              name: 'network-models',
              component: () => import('@/views/network/NetworkModelDesignView.vue'),
              meta: { permission: 'network:view' },
            },
            {
              path: 'devices',
              redirect: '/network/models',
            },
            {
              path: 'topology',
              name: 'network-topology',
              component: () => import('@/views/network/NetworkTopologyDesignView.vue'),
              meta: { permission: 'network:view' },
            },
            {
              path: 'interfaces',
              name: 'network-interfaces',
              component: () => import('@/views/network/NetworkInterfaceDesignView.vue'),
              meta: { permission: 'network:view' },
            },
          ],
        },
        {
          path: 'network/design',
          redirect: '/network/topology',
        },
        {
          path: 'system/users',
          name: 'users',
          component: () => import('@/views/UserView.vue'),
          meta: { permission: 'user:view' },
        },
        {
          path: 'system/roles',
          name: 'roles',
          component: () => import('@/views/RoleView.vue'),
          meta: { permission: 'role:view' },
        },
        {
          path: 'system/audit',
          name: 'audit',
          component: () => import('@/views/AuditView.vue'),
          meta: { permission: 'audit:view' },
        },
        {
          path: 'system/screen',
          name: 'system-screen',
          component: () => import('@/views/ScreenManageView.vue'),
          meta: { screenManage: true },
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.meta.public) {
    if (auth.accessToken) {
      return '/'
    }
    return true
  }

  if (!auth.accessToken) {
    return '/login'
  }

  if (!auth.profile) {
    try {
      await auth.loadProfile()
    } catch {
      auth.clearAuth()
      return '/login'
    }
  }

  const permission = [...to.matched]
    .reverse()
    .find((record) => record.meta.permission)?.meta.permission as string | undefined
  if (permission && !auth.hasPermission(permission)) {
    if (
      to.name === 'rooms-simulate'
      && (auth.hasPermission('datacenter:view') || auth.hasPermission('rack:view'))
    ) {
      return true
    }
    if (
      to.name === 'rooms-manage'
      && !auth.hasPermission('datacenter:view')
      && auth.hasPermission('rack:view')
    ) {
      return { name: 'rack-templates' }
    }
    return '/'
  }

  const needsScreenManage = [...to.matched].some((record) => record.meta.screenManage)
  if (needsScreenManage) {
    const canManageScreen =
      auth.hasPermission('user:view') ||
      auth.hasPermission('role:view') ||
      auth.hasPermission('audit:view') ||
      auth.hasPermission('dashboard:view')
    if (!canManageScreen) return '/'
  }

  if (to.name === 'dashboard-screen') {
    const screen = useScreenStore()
    const isPreview = String(to.query.preview || '') === '1'
    if (!screen.menuEnabled && !isPreview) {
      const canManageScreen =
        auth.hasPermission('user:view') ||
        auth.hasPermission('role:view') ||
        auth.hasPermission('audit:view') ||
        auth.hasPermission('dashboard:view')
      return canManageScreen ? { name: 'system-screen' } : { name: 'dashboard' }
    }
  }

  return true
})

export default router
