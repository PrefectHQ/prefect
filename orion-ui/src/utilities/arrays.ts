export function unique<T extends any[]>(array: T): T {
  return array.filter((v, i, a) => a.indexOf(v) === i) as T
}
