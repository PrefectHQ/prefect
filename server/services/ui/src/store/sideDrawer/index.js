import Drawer from '@/store/sideDrawer/Drawer'

const state = {
  drawer: null,
  open: false
}

const getters = {
  currentDrawer(state) {
    return state.drawer
  },
  isOpen(state) {
    return state.open
  },
  showOpenButton(state) {
    return state.drawer && !state.open
  }
}

const mutations = {
  clearDrawer(state) {
    state.drawer = null
    state.open = false
  },
  close(state) {
    state.open = false
  },
  open(state) {
    state.open = true
  },
  openDrawer(state, drawer) {
    const { type, title, props } = drawer

    state.drawer = new Drawer(type, title, props)
    state.open = true
  }
}

export default {
  getters,
  mutations,
  state,
  namespaced: true
}
