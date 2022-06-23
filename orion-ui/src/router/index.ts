import { RouteGuardExecutioner } from '@prefecthq/orion-design'
import { RouteRecordRaw, createRouter, createWebHistory, RouteComponent, RouterView } from 'vue-router'
import FlowRunsPage from '@/pages/FlowRuns.vue'
import { routes, NamedRoute, AppRouteLocation, AppRouteRecord } from '@/router/routes'
import { BASE_URL } from '@/utilities/meta'

const routeRecords: AppRouteRecord[] = [
  {
    name: 'root',
    path: '/',
    redirect: routes.flowRuns(),
  },
  {
    name: 'flow-runs',
    path: '/runs',
    component: FlowRunsPage,
  },
  {
    path: '/flow-run/:id',
    component: RouterView,
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
    name: 'flows',
    path: '/flows',
    component: (): RouteComponent => import('@/pages/Flows.vue'),
  },
  {
    name: 'flow',
    path: '/flow/:id',
    component: (): RouteComponent => import('@/pages/Flow.vue'),
  },
  {
    name: 'deployments',
    path: '/deployments',
    component: (): RouteComponent => import('@/pages/Deployments.vue'),
  },
  {
    name: 'deployment',
    path: '/deployment/:id',
    component: (): RouteComponent => import('@/pages/Deployment.vue'),
  },
  {
    path: '/work-queues',
    component: RouterView,
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
    ],
  },
  {
    path: '/work-queue/:id',
    component: RouterView,
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
  {
    path: '/blocks',
    component: RouterView,
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
        name: 'blocks.catalog.create',
        path: 'catalog/:blockTypeName/create',
        component: (): RouteComponent => import('@/pages/BlocksCatalogCreate.vue'),
      },
    ],
  },
  {
    path: '/block/:blockDocumentId',
    component: RouterView,
    children: [
      {
        name: 'block',
        path: '',
        component: (): RouteComponent => import('@/pages/Block.vue'),
      },
      {
        name: 'block.edit',
        path: 'edit',
        component: (): RouteComponent => import('@/pages/BlockEdit.vue'),
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
  return RouteGuardExecutioner.after(to, from)
})

export default router
export { routes }
export type { NamedRoute, AppRouteLocation, AppRouteRecord }