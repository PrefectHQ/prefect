import { createApi, PrefectConfig } from '@prefecthq/prefect-ui-library'
import { createActions } from '@prefecthq/vue-compositions'
import { InjectionKey } from 'vue'
import { AdminApi } from '@/services/adminApi'
import { CsrfTokenApi, setupCsrfInterceptor } from '@/services/csrfTokenApi'
import { AxiosInstance } from 'axios'



// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export function createPrefectApi(config: PrefectConfig) {
  const csrfTokenApi = createActions(new CsrfTokenApi(config))

  function axiosInstanceSetupHook(axiosInstance: AxiosInstance) {
    setupCsrfInterceptor(csrfTokenApi, axiosInstance)
  };

  const workspaceApi = createApi(config, axiosInstanceSetupHook)
  return {
    ...workspaceApi,
    csrf: csrfTokenApi,
    admin: createActions(new AdminApi(config, axiosInstanceSetupHook)),
  }
}

export type CreatePrefectApi = ReturnType<typeof createPrefectApi>

export const prefectApiKey: InjectionKey<CreatePrefectApi> = Symbol('PrefectApi')