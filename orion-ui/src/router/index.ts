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
    path: '/queues',
    component: RouterView,
    children: [
      {
        name: 'queues',
        path: '',
        component: (): RouteComponent => import('@/pages/WorkQueues.vue'),
      },
      {
        name: 'create-queue',
        path: 'new',
        component: (): RouteComponent => import('@/pages/WorkQueueCreate.vue'),
      },
    ],
  },
  {
    path: '/queue/:id',
    component: RouterView,
    children: [
      {
        path: 'edit',
        name: 'edit-queue',
        component: (): RouteComponent => import('@/pages/WorkQueueEdit.vue'),
      },
      {
        path: '',
        name: 'queue',
        component: (): RouteComponent => import('@/pages/WorkQueue.vue'),
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