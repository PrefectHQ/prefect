import { RouteLocationNormalized, RouteLocationRaw } from 'vue-router'

export type MaybePromise<T> = T | Promise<T>
export type RouteGuardReturn = MaybePromise<void | Error | RouteLocationRaw | boolean>

export interface RouteGuard {
  before?: (to: RouteLocationNormalized, from: RouteLocationNormalized) => RouteGuardReturn,
  after?: (to: RouteLocationNormalized, from: RouteLocationNormalized) => void,
}