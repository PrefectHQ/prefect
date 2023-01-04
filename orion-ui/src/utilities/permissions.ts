import { Can, workspacePermissions } from '@prefecthq/orion-design'
import { InjectionKey } from 'vue'

const featureFlags = ['access:workers'] as const

export type FeatureFlag = typeof featureFlags[number]

export const permissions = [
  ...workspacePermissions,
  ...featureFlags,
] as const

export type Permission = typeof permissions[number]

export const canKey: InjectionKey<Can<Permission>> = Symbol('canInjectionKey')
