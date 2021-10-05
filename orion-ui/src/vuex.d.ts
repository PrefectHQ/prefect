import { Store } from 'vuex'
import { GlobalFilter } from './typings/global'

declare module '@vue/runtime-core' {
  // declare your own store states
  interface State {
    globalFilter: GlobalFilter
  }

  // provide typings for `this.$store`
  interface ComponentCustomProperties {
    $store: Store<State>
  }
}
