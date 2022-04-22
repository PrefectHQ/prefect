import { InjectionKey } from 'vue'

export const actions = [
  'create',
  'read',
  'update',
  'delete',
] as const
export type Action = typeof actions[number]
export type Access = 'access'

export const workspaceKeys = [
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
export type WorkspaceKey = typeof workspaceKeys[number]
export type WorkspacePermissions = Record<WorkspaceKey, boolean>

export function getWorkspacePermissions(check: (key: WorkspaceKey) => boolean): WorkspacePermissions {
  return workspaceKeys.reduce<WorkspacePermissions>((reduced, key) => ({
    ...reduced,
    [key]: check(key),
  }), {} as WorkspacePermissions)
}

export const accountKeys = [
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
export type AccountKey = typeof accountKeys[number]
export type AccountPermissions = Record<AccountKey, boolean>

export function getAccountPermissions(check: (key: AccountKey) => boolean): AccountPermissions {
  return accountKeys.reduce<AccountPermissions>((reduced, key) => ({
    ...reduced,
    [key]: check(key),
  }), {} as AccountPermissions)
}

export const featureFlags = [
  'billing',
  'collaboration',
] as const
export type FeatureFlag = typeof featureFlags[number]
export type FeatureFlagPermissions = Record<FeatureFlag, boolean>

export function getFeatureFlagPermissions(check: (key: FeatureFlag) => boolean): FeatureFlagPermissions {
  return featureFlags.reduce<FeatureFlagPermissions>((reduced, key) => ({
    ...reduced,
    [key]: check(key),
  }), {} as FeatureFlagPermissions)
}

export type AccountPermissionString = `${Action}:${AccountKey}`
export type WorkspacePermissionString = `${Action}:${WorkspaceKey}`

export type ActionPermissionRecords = Record<Action, Record<WorkspaceKey | AccountKey, boolean>>
export type AccessPermissionRecords = Record<Access, FeatureFlagPermissions>

export type Can = ActionPermissionRecords & AccessPermissionRecords

export const canKey: InjectionKey<Can> = Symbol()