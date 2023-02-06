import { InvalidRouteParamValue, RouteParam } from '@prefecthq/vue-compositions'
import { LocationQueryValue } from 'vue-router'

export class FlowRunParametersRouteParam extends RouteParam<Record<string, unknown>> {

  protected override parse(value: LocationQueryValue): Record<string, unknown> {
    if (value === null) {
      throw new InvalidRouteParamValue()
    }

    return this.format(value)
  }

  protected override format(stringValue: string): Record<string, unknown> {

    const params = new URLSearchParams(stringValue)
    const data: Record<string, unknown> = {}
    for (const [key, value] of params) {
      try {
        console.log(JSON.parse(value))
        data[key] = JSON.parse(value)
      } catch (error) {
        if (value === 'true' || value === 'false') {
          data[key] = value === 'true'
        } else if (!isNaN(parseInt(value))) {
          data[key] = Number(value)
        } else {
          data[key] = value
        }
      }
    }

    return data
  }

}

