import { RouteLocationRaw, RouteRecordName, RouteRecordRaw } from 'vue-router'

export const routes = {
  404: () => ({ name: '404' }) as const,
  block: (blockDocumentId: string) => ({ name: 'block', params: { blockDocumentId } }) as const,
  blockEdit: (blockDocumentId: string) => ({ name: 'block.edit', params: { blockDocumentId } }) as const,
  blocks: () => ({ name: 'blocks' }) as const,
  blocksCatalog: () => ({ name: 'blocks.catalog' }) as const,
  blocksCatalogCreate: (blockTypeSlug: string) => ({ name: 'blocks.create', params: { blockTypeSlug } }) as const,
  blocksCatalogView: (blockTypeSlug: string) => ({ name: 'blocks.view', params: { blockTypeSlug } }) as const,
  deployment: (id: string) => ({ name: 'deployment', params: { id } }) as const,
  deploymentEdit: (id: string) => ({ name: 'edit-deployment', params: { id } }) as const,
  deployments: () => ({ name: 'deployments' }) as const,
  flow: (id: string) => ({ name: 'flow', params: { id } }) as const,
  flowRun: (id: string) => ({ name: 'flow-run', params: { id } }) as const,
  flowRunCreate: (deploymentId: string) => ({ name: 'flow-run.create', params: { deploymentId } }) as const,
  flowRuns: () => ({ name: 'flow-runs' }) as const,
  flows: () => ({ name: 'flows' }) as const,
  notificationCreate: () => ({ name: 'notifications.create' }) as const,
  notificationEdit: (notificationId: string) => ({ name: 'notifications.edit', params: { notificationId } }) as const,
  notifications: () => ({ name: 'notifications' }) as const,
  radar: (id: string) => ({ name: 'radar', params: { id } }) as const,
  root: () => ({ name: 'root' }) as const,
  settings: () => ({ name: 'settings' }) as const,
  taskRun: (id: string) => ({ name: 'task-run', params: { id } }) as const,
  workQueue: (id: string) => ({ name: 'work-queue', params: { id } }) as const,
  workQueueCreate: () => ({ name: 'create-work-queue' }) as const,
  workQueueEdit: (id: string) => ({ name: 'edit-work-queue', params: { id } }) as const,
  workQueues: () => ({ name: 'work-queues' }) as const,
}

export type NamedRoute = ReturnType<typeof routes[keyof typeof routes]>['name']

export function isNamedRoute(route?: RouteRecordName | null): route is NamedRoute {
  return typeof route === 'string' && Object.keys(routes).includes(route)
}

export type AppRouteLocation = Omit<RouteLocationRaw, 'name'> & { name: NamedRoute }
export type AppRouteRecordParent = { name?: NamedRoute, children: AppRouteRecord[] }
export type AppRouteRecordChild = { name: NamedRoute }
export type AppRouteRecord = Omit<RouteRecordRaw, 'name' | 'children'> & AppRouteRecordParent | AppRouteRecordChild