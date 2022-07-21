import { getAppPermissions, isFeatureFlagString } from '@prefecthq/orion-design'
import { reactive } from 'vue'
import { VITE_PREFECT_CANARY } from '@/utilities/meta'

export const can = reactive(
  getAppPermissions(
    permissionString => {
      if (isFeatureFlagString(permissionString)) {
        return VITE_PREFECT_CANARY()
      }

      return true
    },
  ),
)