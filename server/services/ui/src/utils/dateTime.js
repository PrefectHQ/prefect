import { duration } from '@/utils/moment'
import moment from '@/utils/moment'

export const runTimeToEnglish = (startDate, endDate) => {
  if (
    !startDate ||
    !endDate ||
    !(startDate instanceof Date) ||
    !(endDate instanceof Date)
  ) {
    return ''
  }

  const runTimeInMilliseconds = endDate - startDate
  const runTime = duration(runTimeInMilliseconds)

  if (runTimeInMilliseconds === 0) {
    return '0 seconds'
  } else if (runTime >= duration(1, 'week')) {
    return runTime.format('w [weeks], d [days], h [hours]')
  } else if (runTime >= duration(1, 'day')) {
    return runTime.format('d [days], h [hours], m [minutes]')
  } else if (runTime >= duration(1, 'hour')) {
    return runTime.format('h [hours], m [minutes], s [seconds]')
  } else if (runTime >= duration(1, 'minute')) {
    return runTime.format('m [minutes], s [seconds]')
  } else if (runTime >= duration(1, 'second')) {
    return runTime.format('s [seconds]')
  } else if (runTime < duration(1, 'second')) {
    return '~1 second'
  }
  return runTime.humanize()
}

export const durationToEnglish = durationString => {
  if (!durationString) return ''

  const runTime = duration(durationString)

  if (runTime >= duration(1, 'week')) {
    return runTime.format('w [weeks], d [days], h [hours]')
  } else if (runTime >= duration(1, 'day')) {
    return runTime.format('d [days], h [hours], m [minutes]')
  } else if (runTime >= duration(1, 'hour')) {
    return runTime.format('h [hours], m [minutes], s [seconds]')
  } else if (runTime >= duration(1, 'minute')) {
    return runTime.format('m [minutes], s [seconds]')
  } else if (runTime >= duration(1, 'second')) {
    return runTime.format('s [seconds]')
  } else if (runTime < duration(1, 'second')) {
    return '< 1 second'
  }
  return runTime.humanize()
}

export const intervalToEnglish = numberOfMilliseconds => {
  if (numberOfMilliseconds === 604800000) {
    return 'week'
  } else if (numberOfMilliseconds === 86400000) {
    return 'day'
  } else if (numberOfMilliseconds === 3600000) {
    return 'hour'
  } else if (numberOfMilliseconds === 60000) {
    return 'minute'
  }

  const interval = duration(numberOfMilliseconds)

  if (interval > duration(1, 'week')) {
    return interval.format('w [weeks], d [days], h [hours]')
  } else if (interval > duration(1, 'day')) {
    return interval.format('d [days], h [hours], m [minutes]')
  } else if (interval > duration(1, 'hour')) {
    return interval.format('h [hours], m [minutes]')
  } else if (interval > duration(1, 'minute')) {
    return interval.format('m [minutes]')
  } else if (interval < duration(1, 'minute')) {
    return interval.format('s [seconds], ms [ms]')
  }
  return ''
}

export const oneAgo = unitOftime => {
  return moment
    .utc()
    .subtract(1, unitOftime)
    .format()
}
