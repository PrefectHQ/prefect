export function unique<T extends any[]>(array: T): T {
  return array.filter((v, i, a) => a.indexOf(v) === i) as T
}

export function isNonEmptyArray<T extends any[]>(
  array: T | undefined,
): array is T {
  return array !== undefined && array.length > 0
}
