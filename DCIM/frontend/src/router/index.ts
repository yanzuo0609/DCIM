import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
          name: 'datacenters',
          component: () => import('@/views/DatacenterView.vue'),
          meta: { permission: 'datacenter:view' },
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
              path: 'manage',
              name: 'rooms-manage',
              component: () => import('@/views/RoomView.vue'),
              meta: { permission: 'datacenter:view' },
            },
            {
              path: 'templates',
              name: 'room-rack-templates',
              component: () => import('@/views/RackView.vue'),
              meta: { permission: 'rack:view' },
            },
          ],
        },
        {
          path: 'racks',
          redirect: '/rooms/templates',
        },
        {
          path: 'devices',
          name: 'devices',
          component: () => import('@/views/DeviceView.vue'),
          meta: { permission: 'device:view' },
        },
        {
          path: 'devices/contracts',
          name: 'device-contracts',
          component: () => import('@/views/ContractView.vue'),
          meta: { permission: 'device:view' },
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
      to.name === 'rooms-manage'
      && !auth.hasPermission('datacenter:view')
      && auth.hasPermission('rack:view')
    ) {
      return { name: 'room-rack-templates' }
    }
    return '/'
  }

  return true
})

export default router
