
import { Constructor, Api, ApiServer } from '@prefecthq/prefect-ui-library'
import { UiSettings } from '@/services/uiSettings'

export function ApiRoute<T extends Constructor<Api>>(Base: T): T {
  return class ApiRoute extends Base {
    protected override server: ApiServer = UiSettings.get('apiUrl')
  }
}