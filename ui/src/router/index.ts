import { RouteGuardExecutioner, createWorkspaceRouteRecords } from '@prefecthq/prefect-ui-library'
import { RouteRecordRaw, createRouter, createWebHistory, RouteComponent } from 'vue-router'
import { routes, NamedRoute, AppRouteLocation, AppRouteRecord } from '@/router/routes'
import { BASE_URL } from '@/utilities/meta'

const workspaceRoutes = createWorkspaceRouteRecords({
  artifact: () => import('@/pages/Artifact.vue'),
  artifactKey: () => import('@/pages/ArtifactKey.vue'),
  artifacts: () => import('@/pages/Artifacts.vue'),
  flowRuns: () => import('@/pages/FlowRuns.vue'),
  flowRun: () => import('@/pages/FlowRun.vue'),
  flowRunRadar: () => import('@/pages/FlowRunRadar.vue'),
  taskRun: () => import('@/pages/TaskRun.vue'),
  flows: () => import('@/pages/Flows.vue'),
  flow: () => import('@/pages/Flow.vue'),
  deployments: () => import('@/pages/Deployments.vue'),
  deployment: () => import('@/pages/Deployment.vue'),
  deploymentEdit: () => import('@/pages/DeploymentEdit.vue'),
  deploymentFlowRunCreate: () => import('@/pages/FlowRunCreate.vue'),
  workQueues: () => import('@/pages/WorkQueues.vue'),
  workQueue: () => import('@/pages/WorkQueue.vue'),
  workQueueCreate: () => import('@/pages/WorkQueueCreate.vue'),
  workQueueEdit: () => import('@/pages/WorkQueueEdit.vue'),
  blocks: () => import('@/pages/Blocks.vue'),
  blocksCatalog: () => import('@/pages/BlocksCatalog.vue'),
  blocksCatalogView: () => import('@/pages/BlocksCatalogView.vue'),
  blockCreate: () => import('@/pages/BlocksCatalogCreate.vue'),
  block: () => import('@/pages/BlockView.vue'),
  blockEdit: () => import('@/pages/BlockEdit.vue'),
  notifications: () => import('@/pages/Notifications.vue'),
  notificationCreate: () => import('@/pages/NotificationCreate.vue'),
  notificationEdit: () => import('@/pages/NotificationEdit.vue'),
  concurrencyLimit: () => import('@/pages/ConcurrencyLimit.vue'),
  concurrencyLimits: () => import('@/pages/ConcurrencyLimits.vue'),
  variables: () => import('@/pages/Variables.vue'),
  workPool: () => import('@/pages/WorkPool.vue'),
  workPools: () => import('@/pages/WorkPools.vue'),
  workPoolCreate: () => import('@/pages/WorkPoolCreate.vue'),
  workPoolEdit: () => import('@/pages/WorkPoolEdit.vue'),
  workPoolQueue: () => import('@/pages/WorkPoolQueue.vue'),
  workPoolQueueCreate: () => import('@/pages/WorkPoolQueueCreate.vue'),
  workPoolQueueEdit: () => import('@/pages/WorkPoolQueueEdit.vue'),
})

const routeRecords: AppRouteRecord[] = [
  {
    name: 'root',
    path: '/',
    redirect: routes.flowRuns(),
    children: workspaceRoutes,
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
    document.title = 'Prefect Server'
  }

  return RouteGuardExecutioner.after(to, from)
})

export default router
export { routes }
export type { NamedRoute, AppRouteLocation, AppRouteRecord }