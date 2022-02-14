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
  return JSON.parse(JSON.stringify(source))
}