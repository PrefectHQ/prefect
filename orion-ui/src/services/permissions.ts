import { Can, getAppAccountPermissions, getAppWorkspacePermissions, getAppFeatureFlags } from '@prefecthq/orion-design'

export const can: Can = {
  ...getAppAccountPermissions(() => true),
  ...getAppWorkspacePermissions(() => true),
  ...getAppFeatureFlags(() => true),
}