const state = {
  thresholds: {
    // Time before an agent becomes stale
    stale: 1, // minutes since last query
    // Time before an agent becomes unhealthy
    unhealthy: 5 // minutes since last query
  }
}

const getters = {
  staleThreshold(state) {
    return state.thresholds.stale
  },
  unhealthyThreshold(state) {
    return state.thresholds.unhealthy
  }
}

export default {
  getters,
  state,
  namespaced: true
}
