export function flip<K extends string, V extends string>(obj: Record<K, V>): Record<V, K> {
  const result = {} as Record<V, K>

  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      result[obj[key]] = key
    }
  }

  return result
}