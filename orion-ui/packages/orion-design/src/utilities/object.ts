import isDate from 'date-fns/isDate'

export function flip<K extends string, V extends string>(obj: Record<K, V>): Record<V, K> {
  const result = {} as Record<V, K>

  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      result[obj[key]] = key
    }
  }

  return result
}

export function omit<T extends Record<string, unknown>, K extends (keyof T)[]>(source: T, keys: K): Omit<T, K[number]> {
  const copy = { ...source }

  keys.forEach(key => delete copy[key])

  return copy
}

export function clone<T>(source: T): T {
  if (source === null || typeof source !== 'object') {
    return source
  }

  if (isDate(source)) {
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-expect-error
    return new Date(source)
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const copy = new (source as any).constructor()

  for (const key in source) {
    copy[key] = clone(source[key])
  }

  return copy
}