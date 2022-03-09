// Seconds in a year
const _y = 31536000
// Seconds in a day
const _d = 86400
// Seconds in an hour
const _h = 3600
// Seconds in a minute
const _m = 60
// Seconds in a second!
const _s = 1

export const intervals: Record<string, number> = {
  year: _y,
  day: _d,
  hour: _h,
  minute: _m,
  second: _s,
}

function aggregateSeconds(input: number): Record<string, number> {
  const years = Math.floor(input / _y)
  const days = Math.floor(input % _y / _d)
  const hours = Math.floor(input % _y % _d / _h)
  const minutes = Math.floor(input % _y % _d % _h / _m)
  const seconds = Math.ceil(input % _y % _d % _h % _m)

  return { years, days, hours, minutes, seconds }
}

// eslint-disable-next-line max-params
function intervalString(
  type: string,
  seconds: number,
  showOnes: boolean = true,
  showSpaces: boolean = true,
): string {
  return (
    `${seconds === 1 && !showOnes ? '' : seconds
    }${showSpaces ? ' ' : ''}${type}${seconds !== 1 && type.length > 1 ? 's' : ''}`
  )
}

export function secondsToString(
  input: number,
  showOnes: boolean = true,
): string {
  const { years, days, hours, minutes, seconds } = aggregateSeconds(input)
  const _y = intervalString('year', years, showOnes)
  const _d = intervalString('day', days, showOnes)
  const _h = intervalString('hour', hours, showOnes)
  const _m = intervalString('minute', minutes, showOnes)
  const _s = intervalString('second', seconds, showOnes)

  return (
    (years ? `${_y } ` : '') +
    (days ? `${_d } ` : '') +
    (hours ? `${_h } ` : '') +
    (minutes ? `${_m } ` : '') +
    (seconds ? _s : '')
  )
}

export function secondsToApproximateString(
  input: number,
  showOnes: boolean = true,
): string {
  const { years, days, hours, minutes, seconds } = aggregateSeconds(input)
  const _y = intervalString('y', years, showOnes, false)
  const _d = intervalString('d', days, showOnes, false)
  const _h = intervalString('h', hours, showOnes, false)
  const _m = intervalString('m', minutes, showOnes, false)
  const _s = intervalString('s', seconds, showOnes, false)

  if (years > 0 && days == 0) {
    return _y
  }

  if (years > 0 && days > 0) {
    return `${_y } ${ _d}`
  }

  if (days > 0 && hours == 0) {
    return _d
  }

  if (days > 0 && hours > 0) {
    return `${_d } ${ _h}`
  }

  if (hours > 0 && minutes == 0) {
    return `${_h } ${ _m}`
  }

  if (hours > 0 && minutes > 0) {
    return `${_h } ${ _m}`
  }

  if (minutes > 0 && seconds == 0) {
    return _m
  }

  if (minutes > 0 && seconds > 0) {
    return `${_m } ${ _s}`
  }

  return ''
}
