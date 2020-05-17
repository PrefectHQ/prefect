import Vuetify from 'vuetify'
import Vue from 'vue'

// Components
import KeyValueTable from '@/components/KeyValueTable'

//Utitlities
import { createLocalVue, shallowMount } from '@vue/test-utils'

const localVue = createLocalVue()
Vue.use(Vuetify)

describe('Key-Value Table with boolean', () => {
  let wrapper = shallowMount(KeyValueTable, {
    localVue,
    propsData: {
      jsonBlob: {
        required: false
      }
    }
  })
  it('renders a vue instance', () => {
    expect(wrapper.isVueInstance()).toBe(true)
  }),
    it('shows a boolean value', () => {
      expect(wrapper.find('#value').text()).toBe('false')
    })
})

describe('Key-Value Table with integer', () => {
  let wrapper = shallowMount(KeyValueTable, {
    localVue,
    propsData: {
      jsonBlob: {
        version: 5
      }
    }
  })
  it('renders a vue instance', () => {
    expect(wrapper.isVueInstance()).toBe(true)
  }),
    it('shows an integer', () => {
      expect(wrapper.find('#value').text()).toBe('5')
    })
})

describe('Key-Value Table with empty string', () => {
  let wrapper = shallowMount(KeyValueTable, {
    localVue,
    propsData: {
      jsonBlob: {
        name: null
      }
    }
  })
  it('renders a vue instance', () => {
    expect(wrapper.isVueInstance()).toBe(true)
  }),
    it('replaces an empty string with null', () => {
      expect(wrapper.find('#value').text()).toBe('null')
    })
})

describe('Key-Value Table with null', () => {
  let wrapper = shallowMount(KeyValueTable, {
    localVue,
    propsData: {
      jsonBlob: {
        default: null
      }
    }
  })
  it('renders a vue instance', () => {
    expect(wrapper.isVueInstance()).toBe(true)
  }),
    it('replaces null with "null"', () => {
      expect(wrapper.find('#value').text()).toBe('null')
    })
})
