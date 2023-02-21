import { inject } from '@prefecthq/prefect-ui-library'
import { CreatePrefectApi, prefectApiKey } from '@/utilities/api'

export function usePrefectApi(): CreatePrefectApi {
  return inject(prefectApiKey)
}