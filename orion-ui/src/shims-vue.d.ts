/* eslint-disable */
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
declare module '*'
// declare module '../../miter-design/dist/miter-design.umd.js' {
//   const createMiter: PluginInstallFunction
//   export default { createMiter }
// }
