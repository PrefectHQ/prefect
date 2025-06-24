import { createApi, PrefectConfig } from '@prefecthq/prefect-ui-library'
import { createActions } from '@prefecthq/vue-compositions'
import { AxiosInstance } from 'axios'
import { InjectionKey } from 'vue'
import { AdminApi } from '@/services/adminApi'
import { setupApiStatusInterceptor } from '@/services/apiStatus'
import { AutomationsApi } from '@/services/automationsApi'
import { CsrfTokenApi, setupCsrfInterceptor } from '@/services/csrfTokenApi'


// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export function createPrefectApi(config: PrefectConfig) {
  const csrfTokenApi = createActions(new CsrfTokenApi(config))

  function axiosInstanceSetupHook(axiosInstance: AxiosInstance): void {
    setupApiStatusInterceptor(axiosInstance)
    setupCsrfInterceptor(csrfTokenApi, axiosInstance)

    const password = localStorage.getItem('prefect-password')
    if (password) {
      axiosInstance.defaults.headers.common.Authorization = `Basic ${password}`
    }
  }

  const workspaceApi = createApi(config, axiosInstanceSetupHook)

  return {
    ...workspaceApi,
    csrf: csrfTokenApi,
    admin: createActions(new AdminApi(config, axiosInstanceSetupHook)),
    automations: createActions(new AutomationsApi(config, axiosInstanceSetupHook)),
  }
}

export type CreatePrefectApi = ReturnType<typeof createPrefectApi>

export const prefectApiKey: InjectionKey<CreatePrefectApi> = Symbol('PrefectApi')