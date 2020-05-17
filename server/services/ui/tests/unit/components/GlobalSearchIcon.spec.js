// Libraries
import Vuetify from 'vuetify'
import Vue from 'vue'

// Components
import GlobalSearchIcon from '@/components/GlobalSearchIcon'

// Utilities
import { createLocalVue, shallowMount } from '@vue/test-utils'

const localVue = createLocalVue()
Vue.use(Vuetify)

describe('GlobalSearchIcon', () => {
  let vuetify

  beforeEach(() => {
    vuetify = new Vuetify()
  })

  const wrapperProps = input => {
    return {
      localVue,
      vuetify,
      propsData: {
        type: input
      }
    }
  }

  let wrapper = shallowMount(GlobalSearchIcon, wrapperProps('flow'))

  it('renders a vue instance', () => {
    expect(wrapper.isVueInstance()).toBe(true)
  })

  it('should match snapshot', () => {
    expect(wrapper.element).toMatchSnapshot()
  })

  it('should render the avatar element', () => {
    expect(wrapper.find('v-list-item-avatar-stub').exists()).toBe(true)
  })

  it('should render the icon element', () => {
    expect(wrapper.find('v-icon-stub').exists()).toBe(true)
  })

  it('should display the correct icon', () => {
    wrapper = shallowMount(GlobalSearchIcon, wrapperProps('flow'))
    expect(wrapper.find('v-icon-stub').text()).toBe('timeline')

    wrapper = shallowMount(GlobalSearchIcon, wrapperProps('flow_run'))
    expect(wrapper.find('v-icon-stub').text()).toBe('trending_up')

    wrapper = shallowMount(GlobalSearchIcon, wrapperProps('task'))
    expect(wrapper.find('v-icon-stub').text()).toBe('fiber_manual_record')

    wrapper = shallowMount(GlobalSearchIcon, wrapperProps('task_run'))
    expect(wrapper.find('v-icon-stub').text()).toBe('done_all')
  })
})
