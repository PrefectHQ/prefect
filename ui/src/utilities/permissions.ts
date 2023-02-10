import { Can, WorkspacePermission, WorkspaceFeatureFlag } from '@prefecthq/orion-design'
import { InjectionKey } from 'vue'

const featureFlags = ['access:workers', 'access:work_pools'] as const

export type FeatureFlag = typeof featureFlags[number]

export type Permission = FeatureFlag | WorkspacePermission | WorkspaceFeatureFlag

export const canKey: InjectionKey<Can<Permission>> = Symbol('canInjectionKey')
