import { InjectionKey } from 'vue'

export type ToastType = 'default' | 'success' | 'error'
// this type is incomplete
// https://github.com/PrefectHQ/miter-design/blob/24c09337812e8837fc6017e4c855e086d567b62e/src/plugins/Toast/index.ts#L72
export type ShowToast = (message: string, type?: ToastType) => void

export const showToastKey: InjectionKey<ShowToast> = Symbol()