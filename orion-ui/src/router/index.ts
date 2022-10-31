import { RouteGuardExecutioner } from '@prefecthq/orion-design'
import { RouteRecordRaw, createRouter, createWebHistory, RouteComponent } from 'vue-router'
import { routes, NamedRoute, AppRouteLocation, AppRouteRecord } from '@/router/routes'
import { BASE_URL } from '@/utilities/meta'

const routeRecords: AppRouteRecord[] = [
  {
    name: 'root',
    path: '/',
    redirect: routes.flowRuns(),
  },
  {
    path: '/flow-runs',
    children: [
      {
        name: 'flow-runs',
        path: '',
        component: (): RouteComponent => import('@/pages/FlowRuns.vue'),
      },
      {
        path: 'flow-run/:id',
        children: [
          {
            name: 'flow-run',
            path: '',
            component: (): RouteComponent => import('@/pages/FlowRun.vue'),
          },
          {
            name: 'radar',
            path: 'radar',
            component: (): RouteComponent => import('@/pages/FlowRunRadar.vue'),
          },
        ],
      },
      {
        path: 'task-run/:id',
        children: [
          {
            name: 'task-run',
            path: '',
            component: (): RouteComponent => import('@/pages/TaskRun.vue'),
          },
        ],
      },
    ],
  },

  {
    path: '/flows',
    children: [
      {
        name: 'flows',
        path: '',
        component: (): RouteComponent => import('@/pages/Flows.vue'),
      },
      {
        name: 'flow',
        path: 'flow/:id',
        component: (): RouteComponent => import('@/pages/Flow.vue'),
      },
    ],
  },
  {
    path: '/deployments',
    children: [
      {
        name: 'deployments',
        path: '',
        component: (): RouteComponent => import('@/pages/Deployments.vue'),
      },
      {
        path: 'deployment/:id',
        children: [
          {
            name: 'edit-deployment',
            path: 'edit',
            component: (): RouteComponent => import('@/pages/DeploymentEdit.vue'),
          },
          {
            name: 'deployment',
            path: '',
            component: (): RouteComponent => import('@/pages/Deployment.vue'),
          },
          {
            name: 'flow-run.create',
            path: 'run',
            component: (): RouteComponent => import('@/pages/FlowRunCreate.vue'),
          },
        ],
      },
    ],
  },
  {
    path: '/work-queues',
    children: [
      {
        name: 'work-queues',
        path: '',
        component: (): RouteComponent => import('@/pages/WorkQueues.vue'),
      },
      {
        name: 'create-work-queue',
        path: 'new',
        component: (): RouteComponent => import('@/pages/WorkQueueCreate.vue'),
      },
      {
        path: 'work-queue/:id',
        children: [
          {
            path: 'edit',
            name: 'edit-work-queue',
            component: (): RouteComponent => import('@/pages/WorkQueueEdit.vue'),
          },
          {
            path: '',
            name: 'work-queue',
            component: (): RouteComponent => import('@/pages/WorkQueue.vue'),
          },
        ],
      },
    ],
  },
  {
    path: '/blocks',
    children: [
      {
        name: 'blocks',
        path: '',
        component: (): RouteComponent => import('@/pages/Blocks.vue'),
      },
      {
        name: 'blocks.catalog',
        path: 'catalog',
        component: (): RouteComponent => import('@/pages/BlocksCatalog.vue'),
      },
      {
        name: 'blocks.view',
        path: 'catalog/:blockTypeSlug',
        component: (): RouteComponent => import('@/pages/BlocksCatalogView.vue'),
      },
      {
        name: 'blocks.create',
        path: 'catalog/:blockTypeSlug/create',
        component: (): RouteComponent => import('@/pages/BlocksCatalogCreate.vue'),
      },
      {
        path: 'block/:blockDocumentId',
        children: [
          {
            name: 'block',
            path: '',
            component: (): RouteComponent => import('@/pages/BlockView.vue'),
          },
          {
            name: 'block.edit',
            path: 'edit',
            component: (): RouteComponent => import('@/pages/BlockEdit.vue'),
          },
        ],
      },
    ],
  },
  {
    path: '/notifications',
    children: [
      {
        name: 'notifications',
        path: '',
        component: (): RouteComponent => import('@/pages/Notifications.vue'),
      },
      {
        name: 'notifications.create',
        path: 'new',
        component: (): RouteComponent => import('@/pages/NotificationCreate.vue'),
      },
      {
        name: 'notifications.edit',
        path: 'edit/:notificationId',
        component: (): RouteComponent => import('@/pages/NotificationEdit.vue'),
      },
    ],
  },
  {
    name: 'settings',
    path: '/settings',
    component: (): RouteComponent => import('@/pages/Settings.vue'),
  },

  {
    path: '/:pathMatch(.*)*',
    name: '404',
    component: (): RouteComponent => import('@/pages/404.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(BASE_URL()),
  routes: routeRecords as RouteRecordRaw[],
})

router.beforeEach(async (to, from) => {
  return await RouteGuardExecutioner.before(to, from)
})

router.afterEach((to, from) => {
  if (to.fullPath !== from.fullPath) {
    document.title = 'Prefect Orion'
  }

  return RouteGuardExecutioner.after(to, from)
})

export default router
export { routes }
export type { NamedRoute, AppRouteLocation, AppRouteRecord }