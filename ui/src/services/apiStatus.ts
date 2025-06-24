import { showToast } from '@prefecthq/prefect-design'
import { AxiosError, AxiosInstance, isAxiosError } from 'axios'
import { ref } from 'vue'
import ApiStatusToast from '@/components/ApiStatusToast.vue'

const interceptedStatuses = [503]
const interceptedCodes = ['ERR_NETWORK']

const shown = ref(false)

export function setupApiStatusInterceptor(axiosInstance: AxiosInstance): void {
  if (shown.value) {
    return
  }

  const interceptorId = axiosInstance.interceptors.response.use(undefined, interceptor)

  function isInterceptedError(error: AxiosError): boolean {
    return isAxiosError(error) && (interceptedStatuses.includes(error.response?.status ?? 0) || interceptedCodes.includes(error.code ?? ''))
  }

  function interceptor(error: AxiosError): Promise<AxiosError> {
    if (isInterceptedError(error) && !shown.value) {
      shown.value = true
      showToast(ApiStatusToast, 'error', { dismissible: true, timeout: false })
      ejectInterceptor()
    }
    return Promise.reject(error)
  }

  function ejectInterceptor(): void {
    axiosInstance.interceptors.response.eject(interceptorId)
  }
}