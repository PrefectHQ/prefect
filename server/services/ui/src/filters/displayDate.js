import moment from '@/utils/moment'

export default function(timesamptz) {
  if (!timesamptz) {
    return ''
  }

  return moment(timesamptz).format('MMMM Do, YYYY')
}
