import { RouteLocationRaw, RouteRecordName, RouteRecordRaw } from 'vue-router'

export const routes = {
  root: () => ({ name: 'root' }) as const,
  404: () => ({ name: '404' }) as const,
  deployment: (id: string) => ({ name: 'deployment', params: { id } }) as const,
  deployments: () => ({ name: 'deployments' }) as const,
  flow: (id: string) => ({ name: 'flow', params: { id } }) as const,
  flowRun: (id: string) => ({ name: 'flow-run', params: { id } }) as const,
  flowRuns: () => ({ name: 'flow-runs' }) as const,
  flows: () => ({ name: 'flows' }) as const,
  queue: (id: string) => ({ name: 'queue', params: { id } }) as const,
  queueEdit: (id: string) => ({ name: 'edit-queue', params: { id } }) as const,
  queueCreate: () => ({ name: 'create-queue' }) as const,
  queues: () => ({ name: 'queues' }) as const,
  settings: () => ({ name: 'settings' }) as const,
}

export type NamedRoute = ReturnType<typeof routes[keyof typeof routes]>['name']

export function isNamedRoute(route?: RouteRecordName | null): route is NamedRoute {
  return typeof route === 'string' && Object.keys(routes).includes(route)
}

export type AppRouteLocation = Omit<RouteLocationRaw, 'name'> & { name: NamedRoute }
export type AppRouteRecordParent = { name?: NamedRoute, children: AppRouteRecord[] }
export type AppRouteRecordChild = { name: NamedRoute }
export type AppRouteRecord = Omit<RouteRecordRaw, 'name' | 'children'> & AppRouteRecordParent | AppRouteRecordChild