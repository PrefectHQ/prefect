import { RouteGuardExecutioner } from '@prefecthq/orion-design'
import { RouteRecordRaw, createRouter, createWebHistory, RouteComponent } from 'vue-router'
import FlowRunsPage from '@/pages/FlowRuns.vue'
import routes, { routeNames, NamedRoute } from '@/router/routes'
import { BASE_URL } from '@/utilities/meta'

type AppRouteRecord = RouteRecordRaw & { name: NamedRoute }

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
    name: 'flow-run',
    path: '/flow-run/:id',
    component: (): RouteComponent => import('@/pages/FlowRun.vue'),
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
    name: 'queues',
    path: '/queues',
    component: (): RouteComponent => import('@/pages/Queues.vue'),
  },
  {
    name: 'queue',
    path: '/queue/:id',
    component: (): RouteComponent => import('@/pages/Queue.vue'),
  },
  {
    path: '/:pathMatch(.*)*',
    name: '404',
    component: (): RouteComponent => import('@/pages/404.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(BASE_URL()),
  routes: routeRecords,
})

router.beforeEach(async (to, from) => {
  return await RouteGuardExecutioner.before(to, from)
})

router.afterEach((to, from) => {
  return RouteGuardExecutioner.after(to, from)
})

export default router
export { routes, routeNames }
export type { NamedRoute }