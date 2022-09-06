import { showToast } from '@prefecthq/prefect-design'
import { healthApi } from '@/services/healthApi'
import { UiSettings } from '@/services/uiSettings'

export async function healthCheck(): Promise<void> {
  try {
    await healthApi.getHealth()
  } catch (error) {
    const apiUrl = await UiSettings.get('apiUrl').then(res => res)
    showToast(`Can't connect to Orion API at ${apiUrl}. Check that it's accessible from your machine.`, 'error', { timeout: false })
    console.warn(error)
  }
}