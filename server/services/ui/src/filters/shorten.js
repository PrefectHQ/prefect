export default function(string, numberOfCharacters = 8, startingIndex = 0) {
  if (!(typeof string === 'string') || !string) {
    return ''
  }
  return string.substring(startingIndex, startingIndex + numberOfCharacters)
}
