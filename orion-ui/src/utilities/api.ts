import { showToast } from '@prefecthq/prefect-design'
import { healthApi } from '@/services/healthApi'
import { UiSettings } from '@/services/uiSettings'

export async function healthCheck(): Promise<void> {
  console.log('in check')
  try {
    const health = await healthApi.getHealth()
    console.log('health', health)
  } catch (error) {
    console.log('err', error)
    const apiUrl = await UiSettings.get('apiUrl').then(res => res)
    const toastMessage = `Can't connect to Orion API at ${apiUrl}. Check connection or visit https://docs.prefect.io/concepts/settings/ for help`
    showToast(toastMessage, 'error', { timeout: false })
    console.warn(error)
  }
}