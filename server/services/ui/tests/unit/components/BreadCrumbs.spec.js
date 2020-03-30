import { shallowMount } from '@vue/test-utils'

import BreadCrumbs from '@/components/BreadCrumbs'

import Vue from 'vue'
Vue.config.silent = true

describe('BreadCrumbs', () => {
  test('matches snapshots', () => {
    const wrapper = shallowMount(BreadCrumbs, {
      propsData: {
        crumbs: [
          {
            route: {
              name: 'flow',
              params: { id: 'some-flow-id' }
            },
            text: 'second link'
          },
          {
            route: {
              name: 'flow-run',
              params: { id: 'some-flow-run-id' }
            },
            text: 'third-link'
          }
        ]
      }
    })

    expect(wrapper.element).toMatchSnapshot()
  })
})
