import { RouteLocationRaw } from 'vue-router'

type CrumbCallback = () => void

export type Crumb = {
  text?: string | undefined | null,
  loading?: boolean,
  action?: RouteLocationRaw | CrumbCallback,
}

export function crumbIsRouting(crumb?: Crumb): crumb is (Crumb & { action: RouteLocationRaw }) {
  return !!crumb?.action && !crumbIsCallback(crumb)
}

export function crumbIsCallback(crumb?: Crumb): crumb is (Crumb & { action: CrumbCallback }) {
  return typeof crumb?.action === 'function'
}