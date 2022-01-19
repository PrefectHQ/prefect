import { Module } from 'vuex'
import { getters } from './getters'
import { mutations } from './mutations'
import { state, generateInitialGlobalFilterState } from './state'
import type { RootState } from '@/store'
import { GlobalFilter } from '@/typings/global'

const counter: Module<GlobalFilter, RootState> = {
  namespaced: true,
  state,
  getters,
  mutations
}

export default counter
export { generateInitialGlobalFilterState }
