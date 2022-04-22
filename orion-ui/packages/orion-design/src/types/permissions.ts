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

function getFeatureFlagPermissions(check: (key: FeatureFlag) => boolean): FeatureFlagPermissions {
  return featureFlags.reduce<FeatureFlagPermissions>((reduced, key) => ({
    ...reduced,
    [key]: check(key),
  }), {} as FeatureFlagPermissions)
}

export type AccountPermissionString = `${PermissionAction}:${AccountPermissionKey}`
export type WorkspacePermissionString = `${PermissionAction}:${WorkspacePermissionKey}`

export type AppWorkspacePermissions = Record<PermissionAction, Record<WorkspacePermissionKey, boolean>>
export type AppAccountPermissions = Record<PermissionAction, Record<AccountPermissionKey, boolean>>
export type AppFeatureFlags = Record<'access', FeatureFlagPermissions>

export function getAppWorkspacePermissions(check: (action: PermissionAction, key: WorkspacePermissionKey) => boolean): AppWorkspacePermissions {
  return permissionActions.reduce<AppWorkspacePermissions>((result, action) => ({
    ...result,
    [action]: {
      ...getWorkspacePermissions((key) => check(action, key)),
    },
  }), {} as AppWorkspacePermissions)
}

export function getAppAccountPermissions(check: (action: PermissionAction, key: AccountPermissionKey) => boolean): AppAccountPermissions {
  return permissionActions.reduce<AppAccountPermissions>((result, action) => ({
    ...result,
    [action]: {
      ...getAccountPermissions((key) => check(action, key)),
    },
  }), {} as AppAccountPermissions)
}

export function getAppFeatureFlags(check: (key: FeatureFlag) => boolean): AppFeatureFlags {
  return {
    access: {
      ...getFeatureFlagPermissions(check),
    },
  }
}

export type Can = AppWorkspacePermissions & AppFeatureFlags

export const canKey: InjectionKey<Can> = Symbol()