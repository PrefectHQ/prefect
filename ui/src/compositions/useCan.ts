import { Can, inject } from '@prefecthq/orion-design'
import { Permission, canKey } from '@/utilities/permissions'

export function useCan(): Can<Permission> {
  return inject(canKey)
}
