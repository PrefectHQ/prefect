import './global'
import { Toast } from '@prefecthq/miter-design/plugins/Toast/Toast'

declare module '@vue/runtime-core' {
  export interface ComponentCustomProperties {
    $toast: Toast
  }
}
declare interface GlobalFilter {
  start?: Date
  end?: Date
}
