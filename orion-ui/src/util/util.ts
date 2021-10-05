const _y = 31536000, // Seconds in a year
  _d = 86400, // Seconds in a day
  _h = 3600, // Seconds in an hour
  _m = 60, // Seconds in a minute
  _s = 1

export const intervals: { [key: string]: number } = {
  year: _y,
  day: _d,
  hour: _h,
  minute: _m,
  second: _s
}

const aggregateSeconds = (s: number): { [key: string]: number } => {
  const years = Math.floor(s / _y)
  const days = Math.floor((s % _y) / _d)
  const hours = Math.floor(((s % _y) % _d) / _h)
  const minutes = Math.floor((((s % _y) % _d) % _h) / _m)
  const seconds = Math.ceil((((s % _y) % _d) % _h) % _m)

  return { years, days, hours, minutes, seconds }
}

const intervalString = (
  type: string,
  s: number,
  showOnes: boolean = true,
  showSpaces: boolean = true
): string => {
  return (
    (s === 1 && !showOnes ? '' : s) +
    `${showSpaces ? ' ' : ''}${type}${s !== 1 && type.length > 1 ? 's' : ''}`
  )
}

export const secondsToString = (s: number, showOnes: boolean = true) => {
  const { years, days, hours, minutes, seconds } = aggregateSeconds(s)
  const _y = intervalString('year', years, showOnes)
  const _d = intervalString('day', days, showOnes)
  const _h = intervalString('hour', hours, showOnes)
  const _m = intervalString('minute', minutes, showOnes)
  const _s = intervalString('second', seconds, showOnes)

  return (
    (years ? _y + ' ' : '') +
    (days ? _d + ' ' : '') +
    (hours ? _h + ' ' : '') +
    (minutes ? _m + ' ' : '') +
    (seconds ? _s : '')
  )
}

export const secondsToApproximateString = (
  s: number,
  showOnes: boolean = true
): string => {
  const { years, days, hours, minutes, seconds } = aggregateSeconds(s)
  const _y = intervalString('y', years, showOnes, false)
  const _d = intervalString('d', days, showOnes, false)
  const _h = intervalString('h', hours, showOnes, false)
  const _m = intervalString('m', minutes, showOnes, false)
  const _s = intervalString('s', seconds, showOnes, false)

  let value: string = ''

  switch (true) {
    case years > 0 && days == 0:
      value = _y
      break
    case years > 0 && days > 0:
      value = _y + ' ' + _d
      break
    case days > 0 && hours == 0:
      value = _d
      break
    case days > 0 && hours > 0:
      value = _d + ' ' + _h
      break
    case hours > 0 && minutes == 0:
      value = _h + ' ' + _m
      break
    case hours > 0 && minutes > 0:
      value = _h + ' ' + _m
      break
    case minutes > 0 && seconds == 0:
      value = _m
      break
    case minutes > 0 && seconds > 0:
      value = _m + ' ' + _s
      break
    default:
      value = _s
      break
  }

  return value
}
