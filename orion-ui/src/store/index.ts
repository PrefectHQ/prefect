import { GlobalFilter } from '@/typings/global'
import { InjectionKey } from 'vue'
import {
  createStore,
  Store as VuexStore,
  createLogger,
  useStore as baseUseStore
} from 'vuex'
import filter from './filter'

type RootState = {
  filter: GlobalFilter
}

export const key: InjectionKey<VuexStore<RootState>> = Symbol()

const store = createStore<RootState>({
  modules: {
    filter
  },
  plugins: [createLogger()]
})

export function useStore() {
  return baseUseStore(key)
}

export default store
export type { RootState }
