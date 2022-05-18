
import { Constructor, Api, ApiServer } from '@prefecthq/orion-design'
import { UiSettings } from '@/services/uiSettings'

export function ApiRoute<T extends Constructor<Api>>(Base: T): T {
  return class ApiRoute extends Base {
    protected override server: ApiServer = UiSettings.get('apiUrl')
  }
}