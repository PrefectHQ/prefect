import { reactive, watch } from 'vue'
import { Router } from 'vue-router'

class Reactive {
  constructor() {
    return reactive(this)
  }
}

export class UrlQueryParams extends Reactive {
  private readonly router: Router

  private get query() {
    //@ts-expect-error currentRoute is unwrapped
    return this.router.currentRoute.query
  }

  private nestedHandler(filter: string): ProxyHandler<any[] | object> {
    return {
      set: (target, prop, value) => {
        Reflect.set(target, prop, value)

        const filterValue = Reflect.get(this, filter)

        this.router.push({ query: { ...this.query, [filter]: filterValue } })

        return true
      },
      get: (target, prop) => {
        if (prop === '_isProxy') {
          return true
        }

        const value = Reflect.get(target, prop)

        try {
          if (value._isProxy) {
            return value
          }

          return new Proxy(value, this.nestedHandler(filter))
        } catch {
          return value
        }
      }
    }
  }

  private readonly handler: ProxyHandler<UrlQueryParams> = {
    set: (target, prop, value) => {
      Reflect.set(target, prop, value)

      this.router.push({ query: { ...this.query, [prop]: value } })

      return true
    },
    get: (target, prop) => {
      if (prop === '_isProxy') {
        return true
      }

      const value = Reflect.get(target, prop)

      if (typeof prop === 'symbol') {
        return value
      }

      try {
        if (value._isProxy) {
          return value
        }

        return new Proxy(value, this.nestedHandler(prop))
      } catch {
        return value
      }
    }
  }

  public constructor(router: Router) {
    super()

    this.router = router

    watch(
      () => this.query,
      () => this.updateClassFromParams(),
      { deep: true }
    )

    return new Proxy(this, this.handler)
  }

  private updateClassFromParams(): void {
    for (const param in this.query) {
      if (Reflect.has(this, param)) {
        const value = this.query[param]
        const cloned = this.clone(value)
        const parsed = Array.isArray(cloned)
          ? cloned.map(this.parse)
          : this.parse(cloned)

        const current = Reflect.get(this, param)

        if (Array.isArray(current) && !Array.isArray(parsed)) {
          Reflect.set(this, param, [parsed])
        } else {
          Reflect.set(this, param, parsed)
        }
      }
    }
  }

  private clone<T>(value: T): T {
    return JSON.parse(JSON.stringify(value))
  }

  private parse(value: string | null): string | boolean | number | null {
    try {
      return JSON.parse(value!)
    } catch {
      return value
    }
  }
}
