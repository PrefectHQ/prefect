declare module '*.svg' {

  import { VNode } from 'vue'

  type Svg = VNode

  const content: Svg

  // eslint-disable-next-line import/no-default-export
  export default content
}