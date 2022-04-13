
import { Constructor, Api, ApiServer } from '@prefecthq/orion-design'
import { UiSettings } from '@/services/uiSettings'

const defaultApiUrl = 'http://127.0.0.1:4200/api'

export function ApiRoute<T extends Constructor<Api>>(Base: T): T {
  return class ApiRoute extends Base {
    protected override server: ApiServer = UiSettings.get('apiUrl', defaultApiUrl)
  }
}