import { PrefectConfig } from '@prefecthq/prefect-ui-library'
import { UiSettings } from '@/services/uiSettings'
import { MODE } from '@/utilities/meta'

export type UseWorkspaceApiConfig = {
  config: PrefectConfig,
}
export async function useApiConfig(): Promise<UseWorkspaceApiConfig> {
  const baseUrl = await UiSettings.get('apiUrl')
  const config: PrefectConfig = { baseUrl }

  if (baseUrl.startsWith('/') && MODE() === 'development') {
    config.baseUrl = `http://127.0.0.1:4200${baseUrl}`
  }

  return { config }
}