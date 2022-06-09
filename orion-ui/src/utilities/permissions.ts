import { getAppPermissions } from '@prefecthq/orion-design'
import { reactive } from 'vue'
import { VITE_PREFECT_CANARY } from '@/utilities/meta'

export const can = reactive(
  getAppPermissions(
    () => true,
    () => true,
    () => VITE_PREFECT_CANARY(),
  ),
)