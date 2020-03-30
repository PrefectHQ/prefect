// Libraries
import Vuetify from 'vuetify'
import Vue from 'vue'

// Components
import GlobalSearchResult from '@/components/GlobalSearchResult'

// Utilities
import { createLocalVue, shallowMount } from '@vue/test-utils'

const localVue = createLocalVue()
Vue.use(Vuetify)

// Including this for now because the docs don't specify how
// we should be accessing passed-in parent props
// from vuetify components. Would need to combine
// these components to test the parent prop correctly, but
// we only need the specific method for now.
const genFilteredText = text => {
  return `<span>${text}</span>`
}

describe('GlobalSearch', () => {
  let vuetify

  beforeEach(() => {
    vuetify = new Vuetify()
  })

  const wrapperProps = () => {
    return {
      localVue,
      vuetify,
      propsData: {
        searchResult: {
          id: 'a45619e1 - 64ee - 49ac - a121 - b75fbfe5f375',
          name: 'Will I Retry ? Run me to find out.',
          __typename: 'flow'
        },
        parent: { genFilteredText: genFilteredText }
      }
    }
  }

  const wrapper = shallowMount(GlobalSearchResult, wrapperProps())

  it('renders a vue instance', () => {
    expect(wrapper.isVueInstance()).toBe(true)
  })

  it('should match snapshot', () => {
    expect(wrapper.element).toMatchSnapshot()
  })

  it('should contain the search-result class', () => {
    expect(wrapper.classes('search-result')).toBe(true)
  })

  it('should render the title element', () => {
    expect(wrapper.find('v-list-item-title-stub').exists()).toBe(true)
  })

  it('should render the subtitle element', () => {
    expect(wrapper.find('v-list-item-subtitle-stub').exists()).toBe(true)
  })
})
