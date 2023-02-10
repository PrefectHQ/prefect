import 'vue-router'
import { RouteGuard } from '@prefecthq/prefect-ui-library'

declare module 'vue-router' {
  interface RouteMeta {
    guards?: RouteGuard[],
    filters?: { visible?: boolean, disabled?: boolean },
  }
}