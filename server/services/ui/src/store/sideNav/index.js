const state = {
  open: false
}

const getters = {
  isOpen(state) {
    return state.open
  }
}

const mutations = {
  close(state) {
    state.open = false
  },
  open(state) {
    state.open = true
  },
  toggle(state) {
    state.open = !state.open
  }
}

export default {
  getters,
  mutations,
  state,
  namespaced: true
}
