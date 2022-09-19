import { showToast } from '@prefecthq/prefect-design'
import ConnectionToastMessage from '@/components/ConnectionToastMessage.vue'
import { healthApi } from '@/services/healthApi'


export async function healthCheck(): Promise<void> {
  try {
    await healthApi.getHealth()
  } catch (error) {
    showToast(ConnectionToastMessage, 'error', { timeout: false })
    console.warn(error)
  }
}