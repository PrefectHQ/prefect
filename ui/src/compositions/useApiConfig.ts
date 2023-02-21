import { PrefectConfig } from '@prefecthq/prefect-ui-library'
import { UiSettings } from '@/services/uiSettings'

export type UseWorkspaceApiConfig = {
  config: PrefectConfig,
}
export async function useApiConfig(): Promise<UseWorkspaceApiConfig> {
  const baseUrl = await UiSettings.get('apiUrl')
  const config: PrefectConfig = { baseUrl }

  return { config }
}