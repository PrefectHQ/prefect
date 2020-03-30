import moment from 'moment-timezone'

export default function(timestamp) {
  if (!timestamp) {
    return ''
  }
  return moment(timestamp).fromNow()
}
