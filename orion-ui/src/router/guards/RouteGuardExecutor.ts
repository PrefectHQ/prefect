import { RouteLocationNormalized, RouteLocationRaw } from "vue-router";
import { RouteGuard, RouteGuardReturn } from "./RouteGuard";

export class RouteGuardExecutor {
  private static global: RouteGuard[] = []

  public static async before(to: RouteLocationNormalized, from: RouteLocationNormalized): Promise<Awaited<RouteGuardReturn>> {
    const guards = this.getRouteGuards(to)    
    
    for(let guard of guards) {
      const result = await guard.before?.(to, from)

      if(this.isRouteLocation(result)) {
        return result
      }
    }
  }

  public static async after(to: RouteLocationNormalized, from: RouteLocationNormalized):  Promise<void> {
    const guards = this.getRouteGuards(to)

    for(let guard of guards) {
      guard.after?.(to, from)
    }
  }

  public static register(guard: RouteGuard): void {
    this.global.push(guard)
  }

  private static getRouteGuards(route: RouteLocationNormalized): RouteGuard[] {
    const routeGuards = route.meta.guards ?? []

    return [...this.global, ...routeGuards]
  }

  // test this
  private static isRouteLocation(result: RouteGuardReturn): result is RouteLocationRaw {
    return typeof result === 'string' || typeof result == 'object'
  }

}