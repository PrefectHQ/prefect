import { Can, inject } from '@prefecthq/prefect-ui-library'
import { Permission, canKey } from '@/utilities/permissions'

export function useCan(): Can<Permission> {
  return inject(canKey)
}
