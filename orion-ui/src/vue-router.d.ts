import 'vue-router'
import { RouteGuard } from '@prefecthq/orion-design'

declare module 'vue-router' {
  interface RouteMeta {
    guards?: RouteGuard[],
    filters?: { visible?: boolean, disabled?: boolean },
  }
}