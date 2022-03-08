import {
  showPanel as miterShowPanel,
  closePanel as miterClosePanel,
  exitPanel as miterExitPanel
} from '@prefecthq/miter-design'
import { Component } from 'vue'

// any because its a generic constructor
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type InstanceOfComponent = Component & { new (...args: any): any }

export function showPanel<T extends InstanceOfComponent>(component: T, props: InstanceType<T>['$props']): void {
  return miterShowPanel(component, props)
}

export function closePanel(): void {
  return miterClosePanel()
}

export function exitPanel(): void {
  return miterExitPanel()
}
