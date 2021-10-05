import './global'

import { Breakpoints } from '@prefecthq/miter-design/plugins/Breakpoints/Breakpoints'
import { Toast } from '@prefecthq/miter-design/plugins/Toast/Toast'

declare module '@vue/runtime-core' {
  export interface ComponentCustomProperties {
    $toast: Toast
    $breakpoints: Breakpoints
  }
}
declare interface GlobalFilter {
  start?: Date
  end?: Date
}
