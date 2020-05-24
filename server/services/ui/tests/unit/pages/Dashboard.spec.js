// IMPORTANT: Do not remove this import since it mocks all the graphql routes used on the dashboard
// eslint-disable-next-line no-unused-vars
import graphqlMocks from './graphqlMocks'

// Libraries
import Vuetify from 'vuetify'
import Vue from 'vue'

// Components
import Dashboard from '@/pages/Dashboard/Dashboard'

// Utilities
import { createLocalVue, shallowMount } from '@vue/test-utils'

const localVue = createLocalVue()
Vue.use(Vuetify)

describe('Dashboard', () => {
  let vuetify

  beforeEach(() => {
    vuetify = new Vuetify()
  })

  let wrapper = shallowMount(Dashboard, {
    localVue,
    vuetify
  })

  it('renders a vue instance', () => {
    expect(wrapper.isVueInstance()).toBe(true)
  })

  it('should match snapshot', () => {
    expect(wrapper.element).toMatchSnapshot()
  })

  it('should properly mount', () => {
    const wrapper = shallowMount(Dashboard, {})

    expect(wrapper.element).toMatchSnapshot()
  })
})
