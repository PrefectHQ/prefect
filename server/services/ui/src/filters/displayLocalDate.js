import moment from 'moment-timezone'
import store from '@/store'

export default function(timestamp) {
  if (!timestamp) {
    return ''
  }
  const timeObj = moment(timestamp).tz(store.getters['user/timezone'])
  const timeString = timeObj
    ? timeObj.format('MMMM Do, YYYY')
    : moment(timestamp).format('MMMM Do, YYYY')
  return timeString
}
