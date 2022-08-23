import { showToast, Toast } from '@prefecthq/prefect-design'
import { onUnmounted } from 'vue'

/**
 * The useToast composition returns a callable that can be used in place of showToast to automatically dismiss any toasts created during the component's lifecycle
 * @returns () => Toast
 */
export function useToast(): typeof showToast {
  const toasts: Toast[] = []

  onUnmounted(() => toasts.forEach(toast => toast.dismiss()))

  return (...args: Parameters<typeof showToast>) => {
    const toast = showToast(...args)
    toasts.push(toast)
    return toast
  }
}