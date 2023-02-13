import { Can, WorkspacePermission, WorkspaceFeatureFlag } from '@prefecthq/prefect-ui-library'
import { InjectionKey } from 'vue'

const featureFlags = ['access:workers', 'access:work_pools'] as const

export type FeatureFlag = typeof featureFlags[number]

export type Permission = FeatureFlag | WorkspacePermission | WorkspaceFeatureFlag

export const canKey: InjectionKey<Can<Permission>> = Symbol('canInjectionKey')
