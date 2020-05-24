import { runTimeToEnglish, durationToEnglish } from '@/utils/dateTime'

describe('runTimeToEnglish', () => {
  const startTime = new Date('2018-12-10T00:00:00')
  const overAWeek = new Date('2018-12-20T04:05:05')
  const lessThanAWeek = new Date('2018-12-12T04:05:05')
  const lessThanADay = new Date('2018-12-10T04:05:05')
  const lessThanAnHour = new Date('2018-12-10T00:05:05')
  const lessThanAMinute = new Date('2018-12-10T00:00:05')
  const lessThanASecond = new Date('2018-12-10T00:00:00.5')

  it('should return empty string with invalid params', () => {
    expect(runTimeToEnglish()).toBe('')
    expect(runTimeToEnglish(startTime)).toBe('')
    expect(runTimeToEnglish('', '')).toBe('')
    expect(runTimeToEnglish(startTime, '')).toBe('')
    expect(runTimeToEnglish('', startTime)).toBe('')
  })

  it('should return "0 seconds" for the same date', () => {
    expect(runTimeToEnglish(startTime, startTime)).toBe('0 seconds')
  })

  it('should return a proper english sentence for interval greater than a week', () => {
    expect(runTimeToEnglish(startTime, overAWeek)).toBe(
      '1 week, 3 days, 4 hours'
    )
  })

  it('should return a proper english sentence for interval less than a week', () => {
    expect(runTimeToEnglish(startTime, lessThanAWeek)).toBe(
      '2 days, 4 hours, 5 minutes'
    )
  })

  it('should return a proper english sentence for interval less than a day', () => {
    expect(runTimeToEnglish(startTime, lessThanADay)).toBe(
      '4 hours, 5 minutes, 5 seconds'
    )
  })

  it('should return a proper english sentence for interval less than an hour', () => {
    expect(runTimeToEnglish(startTime, lessThanAnHour)).toBe(
      '5 minutes, 5 seconds'
    )
  })

  it('should return a proper english sentence for interval less than a minute', () => {
    expect(runTimeToEnglish(startTime, lessThanAMinute)).toBe('5 seconds')
  })

  it('should return a proper english sentence for interval less than a second', () => {
    expect(runTimeToEnglish(startTime, lessThanASecond)).toBe('~1 second')
  })
})

describe('durationToEnglish', () => {
  const overAWeek = '244:00:00'
  const lessThanAWeek = '52:05:00'
  const lessThanADay = '04:05:05'
  const lessThanAnHour = '00:05:05'
  const lessThanAMinute = '00:00:05'
  const lessThanASecond = '00:00:00.183047'

  it('should return empty string with invalid argument', () => {
    expect(durationToEnglish()).toBe('')
    expect(durationToEnglish(undefined)).toBe('')
    expect(durationToEnglish(null)).toBe('')
    expect(durationToEnglish(false)).toBe('')
  })

  it('should return a proper english sentence for interval greater than a week', () => {
    expect(durationToEnglish(overAWeek)).toBe('1 week, 3 days, 4 hours')
  })

  it('should return a proper english sentence for interval less than a week', () => {
    expect(durationToEnglish(lessThanAWeek)).toBe('2 days, 4 hours, 5 minutes')
  })

  it('should return a proper english sentence for interval less than a day', () => {
    expect(durationToEnglish(lessThanADay)).toBe(
      '4 hours, 5 minutes, 5 seconds'
    )
  })

  it('should return a proper english sentence for interval less than an hour', () => {
    expect(durationToEnglish(lessThanAnHour)).toBe('5 minutes, 5 seconds')
  })

  it('should return a proper english sentence for interval less than a minute', () => {
    expect(durationToEnglish(lessThanAMinute)).toBe('5 seconds')
  })

  it('should return a proper english sentence for interval less than a second', () => {
    expect(durationToEnglish(lessThanASecond)).toBe('< 1 second')
  })
})
