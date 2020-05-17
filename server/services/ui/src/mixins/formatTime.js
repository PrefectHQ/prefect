import moment from '@/utils/moment'

export const formatTime = {
  data() {
    return {
      dateFilters: [
        { name: '1 Hour', value: 'hour' },
        { name: '24 Hours', value: 'day' },
        { name: '7 Days', value: 'week' },
        { name: '30 Days', value: 'month' }
      ],
      // querying failures for over 24 hours either goes into endless loading or returns a 504 so shortening for now
      shortDateFilters: [
        { name: '1 Hour', value: 'hour' },
        { name: '24 Hours', value: 'day' }
      ],
      selectedDateFilter: 'day'
    }
  },
  methods: {
    formatTime(timestamp) {
      let timeObj = moment(timestamp).tz(this.timezone),
        shortenedTz = moment()
          .tz(this.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone)
          .zoneAbbr()
      return `${
        timeObj ? timeObj.format('h:mma') : moment(timestamp).format('h:mma')
      } ${shortenedTz}`
    },
    formatTimeRelative(timestamp) {
      let timeObj = moment(timestamp).tz(this.timezone)
      return timeObj ? timeObj.fromNow() : moment(timestamp).fromNow()
    }
  }
}
