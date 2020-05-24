const state = {
  componentKey: 0
}

const getters = {
  componentKey(state) {
    return state.componentKey
  }
}

const mutations = {
  add(state) {
    state.componentKey++
  }
}

export default {
  getters,
  mutations,
  state,
  namespaced: true
}
