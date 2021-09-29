import { Breakpoints } from '@prefect/miter-design/plugins/Breakpoints/Breakpoints'
import { Toast } from '@prefect/miter-design/plugins/Toast/Toast'

declare module '@vue/runtime-core' {
  export interface ComponentCustomProperties {
    $toast: Toast
    $breakpoints: Breakpoints
  }
}
