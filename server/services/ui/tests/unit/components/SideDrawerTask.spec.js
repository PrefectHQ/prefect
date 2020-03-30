import { shallowMount, createLocalVue, RouterLinkStub } from '@vue/test-utils'
import Vuex from 'vuex'
import SideDrawerTask from '@/components/SideDrawerTask'
import duration from '@/filters/duration'
import number from '@/filters/number'

jest.mock('@/graphql/Task/task-drawer.gql', () => {
  return 'a graphql string'
})

const localVue = createLocalVue()
localVue.use(Vuex)

describe('SideDrawerTask', () => {
  const wrapper = shallowMount(SideDrawerTask, {
    data() {
      return {
        task: {
          id: 'ed8527c7-f810-4b1c-a400-afaebc0ce244',
          name: 'Pull SYMC price',
          trigger: '<function all_successful at 0x7fbfdd288c20>',
          type: 'prefect.tasks.core.function.FunctionTask',
          slug: '8446ca22-7038-4ae0-b702-70b2fb0b5a17',
          task_runs: {},
          flow: {
            id: 'e1cc3664-2445-4d6c-86b4-4fdd885a9cba',
            name: 'Core v0.6.0: Stock Flow'
          }
        }
      }
    },
    propsData: {
      genericInput: {
        taskId: 'b80d9a19-8339-44a4-a695-3231cbb72ae6'
      }
    },
    mocks: {
      $apollo: {
        loading: false,
        data: {}
      }
    },
    stubs: {
      RouterLink: RouterLinkStub,
      PrefectSchedule: true,
      VBtn: true,
      VContainer: true,
      VLayout: true,
      VFlex: true
    },
    localVue,
    filters: {
      number,
      duration
    }
  })
  it('is a Vue instance', () => {
    expect(wrapper.isVueInstance()).toBe(true)
  })
  it('shows the task slug', () => {
    expect(wrapper.find('#slug').text()).toBe(
      '8446ca22-7038-4ae0-b702-70b2fb0b5a17'
    )
  })
  it('matches the snapshot', () => {
    expect(wrapper.element).toMatchSnapshot()
  })
})
