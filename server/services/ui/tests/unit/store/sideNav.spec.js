import sideNav from '@/store/sideNav'
import { createLocalVue } from '@vue/test-utils'
import Vuex from 'vuex'

const localVue = createLocalVue()
localVue.use(Vuex)

describe('sideNav Vuex Module', () => {
  const initialState = () => {
    return {
      open: false
    }
  }
  const openState = () => {
    return {
      open: true
    }
  }

  describe('State', () => {
    it('should be initally set to false', () => {
      const state = sideNav.state
      expect(state.open).toBe(false)
    })
  })
  describe('getters', () => {
    let store
    store = new Vuex.Store({
      state: initialState(),
      getters: sideNav.getters,
      mutations: sideNav.mutations
    })

    it('isOpen should return false in initialState', () => {
      expect(store.getters.isOpen).toBe(store.state.open)
    })

    store = new Vuex.Store({
      state: openState(),
      getters: sideNav.getters,
      mutations: sideNav.mutations
    })

    it('isOpen should return true in openState', () => {
      expect(store.getters.isOpen).toBe(store.state.open)
    })
  })

  describe('Mutations', () => {
    let store

    beforeEach(() => {
      store = new Vuex.Store({
        state: initialState(),
        getters: sideNav.getters,
        actions: sideNav.actions,
        mutations: sideNav.mutations
      })
    })
    describe('open', () => {
      it('should set open to true', () => {
        //making sure isOpen is set to false before we call 'open'
        store.commit('close')
        expect(store.getters['isOpen']).toBe(false)
        store.commit('open')
        expect(store.getters['isOpen']).toBe(true)
      })
      it('leave open as true', () => {
        //making sure isOpen is true to check calling 'open' doesn't change state
        store.commit('open')
        expect(store.getters['isOpen']).toBe(true)
        store.commit('open')
        expect(store.getters['isOpen']).toBe(true)
      })
    })
    describe('close', () => {
      it('should set open to false', () => {
        //making sure isOpen is set to true before we call 'close'
        store.commit('open')
        expect(store.getters['isOpen']).toBe(true)
        store.commit('close')
        expect(store.getters['isOpen']).toBe(false)
      })
      it('should leave open as false', () => {
        //making sure isOpen is false to check calling 'close' doesn't change state
        store.commit('close')
        expect(store.getters['isOpen']).toBe(false)
        store.commit('close')
        expect(store.getters['isOpen']).toBe(false)
      })
    })
    describe('toggle', () => {
      it('should switch to the opposite state', () => {
        //making sure toggle changes state irrespective of what isOpen is initially set to
        expect(store.getters['isOpen']).toBe(false)
        store.commit('toggle')
        expect(store.getters['isOpen']).toBe(true)
        store.commit('toggle')
        expect(store.getters['isOpen']).toBe(false)
      })
    })
  })
})
