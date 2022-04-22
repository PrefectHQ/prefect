import { InjectionKey } from 'vue'

const permissionActions = [
  'create',
  'read',
  'update',
  'delete',
] as const
export type PermissionAction = typeof permissionActions[number]

const workspacePermissionKeys = [
  'block',
  'concurrency_limit',
  'deployment',
  'flow',
  'flow_run',
  'log',
  'saved_search',
  'task_run',
  'work_queue',
] as const
export type WorkspacePermissionKey = typeof workspacePermissionKeys[number]
type WorkspacePermissions = Record<WorkspacePermissionKey, boolean>

export function isWorkspacePermissionKey(key: string): key is WorkspacePermissionKey {
  return workspacePermissionKeys.includes(key as WorkspacePermissionKey)
}

function getWorkspacePermissions(check: (key: WorkspacePermissionKey) => boolean): WorkspacePermissions {
  return workspacePermissionKeys.reduce<WorkspacePermissions>((reduced, key) => ({
    ...reduced,
    [key]: check(key),
  }), {} as WorkspacePermissions)
}

const accountPermissionKeys = [
  'account',
  'account_membership',
  'account_role',
  'bot',
  'invitation',
  'team',
  'team',
  'workspace',
  'workspace_bot_access',
  'workspace_role',
  'workspace_user_access',
] as const
export type AccountPermissionKey = typeof accountPermissionKeys[number]
type AccountPermissions = Record<AccountPermissionKey, boolean>

export function isAccountPermissionKey(key: string): key is AccountPermissionKey {
  return accountPermissionKeys.includes(key as AccountPermissionKey)
}

function getAccountPermissions(check: (key: AccountPermissionKey) => boolean): AccountPermissions {
  return accountPermissionKeys.reduce<AccountPermissions>((reduced, key) => ({
    ...reduced,
    [key]: check(key),
  }), {} as AccountPermissions)
}

const featureFlags = [
  'billing',
  'collaboration',
] as const
export type FeatureFlag = typeof featureFlags[number]
type FeatureFlagPermissions = Record<FeatureFlag, boolean>

export function isFeatureFlag(key: string): key is FeatureFlag {
  return featureFlags.includes(key as FeatureFlag)
}

function getFeatureFlagPermissions(check: (key: FeatureFlag) => boolean): FeatureFlagPermissions {
  return featureFlags.reduce<FeatureFlagPermissions>((reduced, key) => ({
    ...reduced,
    [key]: check(key),
  }), {} as FeatureFlagPermissions)
}

export type AccountPermissionString = `${PermissionAction}:${AccountPermissionKey}`
export type WorkspacePermissionString = `${PermissionAction}:${WorkspacePermissionKey}`

export type AppPermissions = Record<PermissionAction, Record<AccountPermissionKey, boolean> & Record<WorkspacePermissionKey, boolean>>
export type AppFeatureFlags = Record<'access', FeatureFlagPermissions>

export function getAppPermissions(check: (action: PermissionAction, key: AccountPermissionKey | WorkspacePermissionKey) => boolean): AppPermissions {
  return permissionActions.reduce<AppPermissions>((result, action) => ({
    ...result,
    [action]: {
      ...getAccountPermissions((key) => check(action, key)),
      ...getWorkspacePermissions((key) => check(action, key)),
    },
  }), {} as AppPermissions)
}

export function getAppFeatureFlags(check: (key: FeatureFlag) => boolean): AppFeatureFlags {
  return {
    access: {
      ...getFeatureFlagPermissions(check),
    },
  }
}

export type Can = AppPermissions & AppFeatureFlags

export const canKey: InjectionKey<Can> = Symbol()