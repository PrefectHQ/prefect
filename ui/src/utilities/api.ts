import { createApi, PrefectConfig } from '@prefecthq/prefect-ui-library'
import { createActions } from '@prefecthq/vue-compositions'
import { InjectionKey } from 'vue'
import { AdminApi } from '@/services/adminApi'

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export function createPrefectApi(config: PrefectConfig) {
  const workspaceApi = createApi(config)

  return {
    ...workspaceApi,
    admin: createActions(new AdminApi(config)),
  }
}

export type CreatePrefectApi = ReturnType<typeof createPrefectApi>

export const prefectApiKey: InjectionKey<CreatePrefectApi> = Symbol('PrefectApi')