export function snakeCase(string: string) {
  return string
    .replace(/\W+/g, ' ')
    .split(/ |\B(?=[A-Z])/)
    .map((word) => word.toLowerCase())
    .join('_')
}

export function toPluralString(word: string, count: number) {
  if (count == 1) {
    return word
  }

  const ending = ['s', 'sh', 'ch', 'x', 'z'].some((chars) =>
    word.endsWith(chars)
  )
    ? 'es'
    : 's'

  return `${word}${ending}`
}
