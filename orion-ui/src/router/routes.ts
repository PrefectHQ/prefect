import { RouteLocationRaw, RouteRecordName } from 'vue-router'

export const routeNames = [
  'deployment',
  'deployments',
  'flow-run',
  'flow-runs',
  'flow',
  'flows',
  'queue',
  'queues',
  'root',
  'settings',
] as const

export type NamedRoute = typeof routeNames[number]

export function isNamedRoute(route?: RouteRecordName | null): route is NamedRoute {
  return typeof route === 'string' && routeNames.map(x => x as string).includes(route)
}

export type AppRouteLocation = Exclude<RouteLocationRaw, string> & { name: NamedRoute }

const routes = {
  deployment: (id: string) => ({ name: 'deployment', params: { id } }),
  deployments: () => ({ name: 'deployments' }),
  flow: (id: string) => ({ name: 'flow', params: { id } }),
  flowRun: (id: string) => ({ name: 'flow-run', params: { id } }),
  flowRuns: () => ({ name: 'flow-runs' }),
  flows: () => ({ name: 'flows' }),
  queue: (id: string) => ({ name: 'queue', params: { id } }),
  queueCreate: () => ({ name: 'queue-create' }),
  queues: () => ({ name: 'queues' }),
  settings: (): AppRouteLocation => ({ name: 'settings' }),
}

export default routes