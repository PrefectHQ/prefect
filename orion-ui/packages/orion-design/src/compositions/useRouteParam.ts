import { computed, Ref } from 'vue'
import { RouteParamValue, useRoute } from 'vue-router'
import { ErrorMissingRouterParam } from '@/models/ErrorMissingRouterParam'

export function useRouteParam(param: string): Ref<RouteParamValue> {
  const route = useRoute()

  return computed(() => {
    let paramValue = route.params[param]

    if (Array.isArray(paramValue)) {
      if (!paramValue.length) {
        console.warn(new ErrorMissingRouterParam(param))
        // throw new ErrorMissingRouterParam(param)
      }

      [paramValue] = paramValue
    }

    if (!paramValue || paramValue.length === 0) {
      console.warn(new ErrorMissingRouterParam(param))
      // throw new ErrorMissingRouterParam(param)
    }

    return paramValue
  })
}