import { InjectionKey } from 'vue'

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

export const featureFlags = [
  'billing',
  'collaboration',
] as const
export type Access = 'access'
export type FeatureFlag = typeof featureFlags[number]

export const actions = [
  'create',
  'read',
  'update',
  'delete',
] as const
export type Action = typeof actions[number]


export type ActionPermissions = Record<Action, Record<WorkspaceKey | AccountKey, boolean>>
export type FeatureFlagPermissions = Record<Access, Record<FeatureFlag, boolean>>

export type AccountPermissionString = `${Action}:${AccountKey}`
export type WorkspacePermissionString = `${Action}:${WorkspaceKey}`

export type Can = ActionPermissions & FeatureFlagPermissions

export const canKey: InjectionKey<Can> = Symbol()