import { mocker } from '../services'

const characters = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z'] as const

export function randomChar(): typeof characters[number] {
  return characters[Math.floor(Math.random() * characters.length)]
}

export function randomString(chars?: number): string {
  if (!chars) {
    chars = mocker.create('number', [5, 10])
  }

  return new Array(chars).fill(null).map(() => mocker.create('char')).join('')
}

export function randomSentence(words?: number): string {
  if (!words) {
    words = mocker.create('number', [5, 10])
  }

  const [first, ...rest] = new Array(words).fill(null).map(() => mocker.create('string'))

  return `${first.charAt(0).toUpperCase()}${first.slice(1)} ${rest.join(' ')}.`
}

export function randomParagraph(sentences?: number): string {
  if (!sentences) {
    sentences = mocker.create('number', [2, 10])
  }

  return new Array(sentences).fill(null).map(() => mocker.create('sentence')).join(' ')
}
