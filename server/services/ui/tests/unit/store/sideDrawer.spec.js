import sideDrawer from '@/store/sideDrawer'
import { createLocalVue } from '@vue/test-utils'
import Vuex from 'vuex'
import Drawer from '@/store/sideDrawer/Drawer'

const localVue = createLocalVue()
localVue.use(Vuex)

describe('sideDrawer Vuex Module', () => {
  const initialState = () => {
    return {
      drawer: null,
      open: false
    }
  }
  const openState = () => {
    return {
      drawer: new Drawer('SideDrawerRecentFailures', 'Recent Failures', {}),
      open: true
    }
  }

  const closedState = () => {
    return {
      drawer: new Drawer('SideDrawerRecentFailures', 'Recent Failures', {}),
      open: false
    }
  }

  describe(' Initial State', () => {
    describe('state.open', () => {
      it('should be initally set to false', () => {
        const state = sideDrawer.state
        expect(state.open).toEqual(false)
      })
    })
    describe('state.drawer', () => {
      it('should initially be null', () => {
        const state = sideDrawer.state
        expect(state.drawer).toEqual(null)
      })
    })
  })

  describe('getters', () => {
    describe('getters in initial state', () => {
      let store
      beforeEach(() => {
        store = new Vuex.Store({
          state: initialState(),
          getters: sideDrawer.getters,
          mutations: sideDrawer.mutations
        })
      })

      it('isOpen should return false in initialState', () => {
        expect(store.getters.isOpen).toBe(store.state.open)
      })
      it('currentDrawer should return null in initialState', () => {
        expect(store.getters.currentDrawer).toBe(store.state.drawer)
      })
      it('showOpenButton should return false in initialState', () => {
        expect(store.getters.showOpenButton).toBeFalsy()
      })
    })

    describe('getters in open state', () => {
      let store
      beforeEach(() => {
        store = new Vuex.Store({
          state: openState(),
          getters: sideDrawer.getters,
          mutations: sideDrawer.mutations
        })
      })

      it('isOpen should return true in openState', () => {
        expect(store.getters.isOpen).toBe(store.state.open)
      })
      it('currentDrawer should return a drawer with type in openState', () => {
        expect(store.getters.currentDrawer).toBe(store.state.drawer)
      })
      it('showOpenButton should return false  in openState (where the drawer is loaded and open)', () => {
        expect(store.getters.showOpenButton).toBeFalsy()
      })
    })

    describe('getters in closed state', () => {
      let store
      beforeEach(() => {
        store = new Vuex.Store({
          state: closedState(),
          getters: sideDrawer.getters,
          mutations: sideDrawer.mutations
        })
      })
      it('showOpenButton should return true if the drawer is loaded but closed', () => {
        expect(store.getters.showOpenButton).toBeTruthy()
      })
    })
  })
  describe('Mutations', () => {
    let store

    beforeEach(() => {
      store = new Vuex.Store({
        state: initialState(),
        getters: sideDrawer.getters,
        actions: sideDrawer.actions,
        mutations: sideDrawer.mutations
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

    describe('clearDrawer', () => {
      beforeEach(() => {
        store = new Vuex.Store({
          state: openState(),
          getters: sideDrawer.getters,
          actions: sideDrawer.actions,
          mutations: sideDrawer.mutations
        })
      })

      it('should set open to false and drawer to null', () => {
        store.commit('clearDrawer')
        expect(store.getters['isOpen']).toBe(false)
        expect(store.getters['currentDrawer']).toBe(null)
      })
    })
    describe('openDrawer', () => {
      beforeEach(() => {
        store = new Vuex.Store({
          state: openState(),
          getters: sideDrawer.getters,
          actions: sideDrawer.actions,
          mutations: sideDrawer.mutations
        })
      })

      it('should set open to true and set a drawer', () => {
        store.commit('openDrawer', { type: 'a', title: 'b' })
        expect(store.getters['isOpen']).toBe(true)
        expect(store.getters['currentDrawer'].type).toBe('a')
      })
    })
  })
})
