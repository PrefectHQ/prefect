export const intervals = {
  year: 31536000,
  day: 86400,
  hour: 3600,
  minute: 60,
  second: 1,
} as const

type IntervalTypes = keyof typeof intervals
type IntervalTypesShort = 'y'|'d'|'h'|'m'|'s'
type IntervalTypesPlural = `${keyof typeof intervals}s`

function aggregateSeconds(input: number): Record<IntervalTypesPlural, number> {
  const years = Math.floor(input / intervals.year)
  const days = Math.floor(input % intervals.year / intervals.day)
  const hours = Math.floor(input % intervals.year % intervals.day / intervals.hour)
  const minutes = Math.floor(input % intervals.year % intervals.day % intervals.hour / intervals.minute)
  const seconds = Math.ceil(input % intervals.year % intervals.day % intervals.hour % intervals.minute)

  return { years, days, hours, minutes, seconds }
}

function intervalStringSeconds(seconds: number, showOnes = true): string {
  return `${seconds === 1 && !showOnes ? '' : seconds}`
}

function intervalStringIntervalType(type: IntervalTypes, seconds: number, showOnes = true): string {
  return `${intervalStringSeconds(seconds, showOnes)} ${type}${seconds !== 1 ? 's' : ''}`
}

function intervalStringSecondsIntervalTypeShort(type: IntervalTypesShort, seconds: number, showOnes = true): string {
  return `${intervalStringSeconds(seconds, showOnes)}${type}`
}

export function secondsToString(input: number, showOnes = true): string {
  const { years, days, hours, minutes, seconds } = aggregateSeconds(input)
  const year = years ? intervalStringIntervalType('year', years, showOnes) : ''
  const day = days ? intervalStringIntervalType('day', days, showOnes) : ''
  const hour = hours ? intervalStringIntervalType('hour', hours, showOnes) : ''
  const minute = minutes ? intervalStringIntervalType('minute', minutes, showOnes) : ''
  const second = seconds ? intervalStringIntervalType('second', seconds, showOnes) : ''

  return [year, day, hour, minute, second].map(x => x ? x : '').join(' ')
}

export function secondsToApproximateString(input: number, showOnes = true): string {
  const { years, days, hours, minutes, seconds } = aggregateSeconds(input)
  const year = intervalStringSecondsIntervalTypeShort('y', years, showOnes)
  const day = intervalStringSecondsIntervalTypeShort('d', days, showOnes)
  const hour = intervalStringSecondsIntervalTypeShort('h', hours, showOnes)
  const minute = intervalStringSecondsIntervalTypeShort('m', minutes, showOnes)
  const second = intervalStringSecondsIntervalTypeShort('s', seconds, showOnes)

  switch (true) {
    case years > 0 && days == 0:
      return year
    case years > 0 && days > 0:
      return `${year } ${ day}`
    case days > 0 && hours == 0:
      return day
    case days > 0 && hours > 0:
      return `${day } ${ hour}`
    case hours > 0 && minutes == 0:
      return `${hour } ${ minute}`
    case hours > 0 && minutes > 0:
      return `${hour } ${ minute}`
    case minutes > 0 && seconds == 0:
      return minute
    case minutes > 0 && seconds > 0:
      return `${minute } ${ second}`
    default:
      return second
  }
}