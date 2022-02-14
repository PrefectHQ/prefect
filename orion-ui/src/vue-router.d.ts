import 'vue-router'
import { RouteGuard } from './router/guards/RouteGuard';

declare module 'vue-router' {
  interface RouteMeta {
    guards?: RouteGuard[]
  }
}