export type KeysMatching<T, V> = {
  [K in keyof T]-?: T[K] extends V ? K : never
}[keyof T]

export type Require<T, K extends keyof T> = Omit<T, K> & Required<Pick<T, K>>