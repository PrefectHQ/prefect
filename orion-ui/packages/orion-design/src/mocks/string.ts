import { mocker } from '../services'

const characters = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z'] as const

export function randomChar(): typeof characters[number] {
  return characters[Math.floor(Math.random() * characters.length)]
}

export function randomString(len?: number): string {
  if (!len) {
    len = mocker.create('number', [5, 10])
  }

  return new Array(len).fill(null).map(() => mocker.create('char')).join('')
}

export function randomSentence(words?: number): string {
  if (!words) {
    words = mocker.create('number', [5, 10])
  }

  const [first, ...rest] = new Array(words).fill(null).map(() => mocker.create('string'))

  return `${first.charAt(0).toUpperCase()}${first.slice(1)} ${rest.join(' ')}.`
}

export function randomParagraph(paragraphs?: number): string {
  if (!paragraphs) {
    paragraphs = mocker.create('number', [5, 10])
  }

  function getParagraph(): string {
    return new Array(mocker.create('number', [2, 10])).fill(null).map(() => mocker.create('sentence')).join(' ')
  }

  return new Array(paragraphs).fill(null).map(getParagraph).join('\n\n')
}