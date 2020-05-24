import shorten from '@/filters/shorten'

describe('shorten filter', () => {
  it('should take a string and return the first 8 characters by default', () => {
    const testString = '2018-12-11T19:38:22.736697'

    const shortenedString = shorten(testString)
    expect(shortenedString).toBe('2018-12-')
  })

  it('should take a string and return the provided number of characters', () => {
    const testString = '2018-12-11T19:38:22.736697'

    const shortenedString = shorten(testString, 5)
    expect(shortenedString).toBe('2018-')
  })

  it('should take a string and adhere to the starting and ending character requirements', () => {
    const testString = '2018-12-11T19:38:22.736697'

    const shortenedString = shorten(testString, 2, 5)
    expect(shortenedString).toBe('12')
  })

  it('should accept no parameters and return an empty string', () => {
    expect(shorten()).toBe('')
  })

  it('should accept a non-string as a parameter and return an empty string', () => {
    expect(shorten(12452345)).toBe('')
  })
})
