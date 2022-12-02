import { createWorkspaceRoutes } from '@prefecthq/orion-design'
import { RouteLocationRaw, RouteRecordName, RouteRecordRaw } from 'vue-router'

export const routes = {
  root: () => ({ name: 'root' }) as const,
  404: () => ({ name: '404' }) as const,
  settings: () => ({ name: 'settings' }) as const,
  ...createWorkspaceRoutes(),
}

export type NamedRoute = ReturnType<typeof routes[keyof typeof routes]>['name']

export function isNamedRoute(route?: RouteRecordName | null): route is NamedRoute {
  return typeof route === 'string' && Object.keys(routes).includes(route)
}

export type AppRouteLocation = Omit<RouteLocationRaw, 'name'> & { name: NamedRoute }
export type AppRouteRecordParent = { name?: NamedRoute, children: AppRouteRecord[] }
export type AppRouteRecordChild = { name: NamedRoute }
export type AppRouteRecord = Omit<RouteRecordRaw, 'name' | 'children'> & AppRouteRecordParent | AppRouteRecordChild