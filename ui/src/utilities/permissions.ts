import { Can, WorkspacePermission, WorkspaceFeatureFlag } from '@prefecthq/prefect-ui-library'
import { InjectionKey } from 'vue'

const featureFlags = [
  'access:workers',
  'access:work_pools',
  'access:artifacts',
  'access:deploymentStatus',
  'access:workQueueStatus',
  'access:flowRunInfraOverrides',
] as const

export type FeatureFlag = typeof featureFlags[number] | WorkspaceFeatureFlag

export type Permission = FeatureFlag | WorkspacePermission

export const canKey: InjectionKey<Can<Permission>> = Symbol('canInjectionKey')
