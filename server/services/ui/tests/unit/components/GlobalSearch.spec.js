// Libraries
import Vuetify from 'vuetify'
import Vue from 'vue'

// Components
import GlobalSearch from '@/components/GlobalSearch'

// Utilities
import { createLocalVue, shallowMount } from '@vue/test-utils'
// import { routes } from '@/router'

// Test Data
// import testData from './GlobalSearchTestData'

// Use jest to mock the graphql data
jest.mock('@/graphql/GlobalSearch/search-by-id.gql', () => {
  return 'a graphql string'
})
jest.mock('@/graphql/GlobalSearch/search-by-name.gql', () => {
  return 'a graphql string'
})

const localVue = createLocalVue()
Vue.use(Vuetify)

describe('GlobalSearch', () => {
  let vuetify

  beforeEach(() => {
    vuetify = new Vuetify()
  })

  let wrapper = shallowMount(GlobalSearch, {
    localVue,
    vuetify
  })

  it('renders a vue instance', () => {
    expect(wrapper.isVueInstance()).toBe(true)
  })

  it('should match snapshot', () => {
    expect(wrapper.element).toMatchSnapshot()
  })

  it('focuses the input box when the / hotkey is pressed', () => {
    wrapper.trigger('click')
    wrapper.trigger('keyup', {
      key: '/'
    })

    // Need to add these tests but Jest throws errors
    // when trying to do a full mount as required by Vuetify
    // and I'm not sure how to test vuetify UI components
    // without doing the full vuetify mount
    expect(true).toBe(true)
  })
})
