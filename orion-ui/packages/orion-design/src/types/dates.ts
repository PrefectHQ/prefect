export type DateString = string

export type DatePartShort = 'h' | 'd' | 'w' | 'm' | 'y'

export function isDatePartShort(input: string): input is DatePartShort {
  return ['h', 'd', 'w', 'm', 'y'].includes(input)
}