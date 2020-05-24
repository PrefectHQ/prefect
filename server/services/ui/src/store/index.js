// Core
import Vue from 'vue'
import Vuex from 'vuex'

// Modules
import agent from '@/store/agent'
import refresh from '@/store/refresh'
import sideDrawer from '@/store/sideDrawer'
import sideNav from '@/store/sideNav'

Vue.use(Vuex)

const store = new Vuex.Store({
  modules: {
    agent,
    refresh,
    sideDrawer,
    sideNav
  },
  strict: process.env.NODE_ENV !== 'production'
})

export default store
