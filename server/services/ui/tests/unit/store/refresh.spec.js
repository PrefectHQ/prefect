import store from '@/store'

describe('Refresh Vuex Module', () => {
  it('has a key that starts at 0', () => {
    expect(store.getters['refresh/componentKey']).toBe(0)
  })

  it('has a key that increases by 1 when add is called', () => {
    expect(store.getters['refresh/componentKey']).toBe(0)
    store.commit('refresh/add')
    expect(store.getters['refresh/componentKey']).toBe(1)
  })
})
