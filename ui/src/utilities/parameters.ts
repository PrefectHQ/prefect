import { RouteParam } from '@prefecthq/vue-compositions'
import { LocationQueryValue } from 'vue-router'

export class JSONRouteParam extends RouteParam<Record<string, unknown>> {

  protected override parse(value: LocationQueryValue): Record<string, unknown> {
    return JSON.parse(decodeURIComponent(value ?? ''))
  }

  protected override format(value: Record<string, unknown>): LocationQueryValue {
    return encodeURIComponent(JSON.stringify(value))
  }
}