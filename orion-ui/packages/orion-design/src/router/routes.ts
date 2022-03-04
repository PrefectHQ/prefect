import { InjectionKey } from 'vue'
import { RouteLocationRaw } from 'vue-router'

export const workspaceDashboardKey: InjectionKey<RouteLocationRaw> = Symbol()