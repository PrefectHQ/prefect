import { shallowMount } from '@vue/test-utils'
import PrefectSchedule from '@/components/PrefectSchedule'

describe('PrefectSchedule', () => {
  describe('Snapshots', () => {
    it('should properly display a cron schedule with no timezone', () => {
      const wrapper = shallowMount(PrefectSchedule, {
        propsData: {
          schedule: {
            type: 'CronSchedule',
            cron: '0 12 * * *'
          }
        }
      })

      expect(wrapper.element).toMatchSnapshot()
    })

    it('should properly display a cron schedule with a timezone', () => {
      const wrapper = shallowMount(PrefectSchedule, {
        propsData: {
          schedule: {
            type: 'CronSchedule',
            cron: '0 12 * * *',
            start_date: {
              tz: 'EST'
            }
          }
        }
      })

      expect(wrapper.element).toMatchSnapshot()
    })

    it('should properly display an interval schedule', () => {
      const wrapper = shallowMount(PrefectSchedule, {
        propsData: {
          schedule: {
            type: 'IntervalSchedule',
            interval: '60000000'
          }
        }
      })

      expect(wrapper.element).toMatchSnapshot()
    })

    it('should properly display an Union schedule', () => {
      const wrapper = shallowMount(PrefectSchedule, {
        propsData: {
          schedule: {
            type: 'UnionSchedule'
          }
        },
        stubs: ['VBtn']
      })

      expect(wrapper.element).toMatchSnapshot()
    })

    it('should properly display an custom schedule', () => {
      const wrapper = shallowMount(PrefectSchedule, {
        propsData: {
          schedule: {
            type: 'Schedule'
          }
        },
        stubs: ['VBtn']
      })

      expect(wrapper.element).toMatchSnapshot()
    })
  })
})
