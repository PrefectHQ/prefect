import { STATE_NAMES } from '@/utils/states.js'

export const heartbeatMixin = {
  data() {
    return { state: 'All', stateNames: STATE_NAMES, stateList: [] }
  },
  computed: {
    checkedState() {
      if (this.state === 'All') return null
      if (!this.state) return null
      return this.state
    },
    states() {
      if (this.state === 'All') {
        return this.list()
      }
      return this.stateList
    }
  },
  methods: {
    list() {
      if (this.state === 'All') {
        const list = this.heartbeat ? this.heartbeat.map(run => run.state) : []
        list.unshift('All')
        this.stateList = list
        return list
      }
    }
  }
}
