import { FilterObject } from '..'

export class KeyValueStore<K, V> {
  private readonly keyMap = new Map<K, V>()
  private readonly valueMap = new Map<V, K>()

  public constructor(entries?: readonly (readonly [K, V])[] | null) {
    entries?.forEach(([key, value]) => {
      this.set(key, value)
    })
  }

  public getValue(key: K): V | undefined {
    return this.keyMap.get(key)
  }

  public getKey(value: V): K | undefined {
    return this.valueMap.get(value)
  }

  public has(key: K, value: V): boolean {
    return this.keyMap.has(key) && this.valueMap.has(value)
  }

  public hasKey(key: K): boolean {
    return this.keyMap.has(key)
  }

  public hasValue(value: V): boolean {
    return this.valueMap.has(value)
  }

  public set(key: K, value: V): this {
    this.keyMap.set(key, value)
    this.valueMap.set(value, key)

    return this
  }

  public delete(key: K, value: V): boolean {
    this.keyMap.delete(key)
    this.valueMap.delete(value)

    return true
  }

  public clear(): boolean {
    this.keyMap.clear()
    this.valueMap.clear()

    return true
  }
}

const store = new KeyValueStore<FilterObject, string>([['flow', 'f']])

const test = store.getKey('f')
const test2 = store.getValue('flow')