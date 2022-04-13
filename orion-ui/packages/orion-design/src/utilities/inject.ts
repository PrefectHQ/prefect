import { inject as vueInject, InjectionKey } from 'vue'

export function inject<T>(key: InjectionKey<T> | string): T {
  const value = vueInject(key)

  if (value === undefined) {
    throw `Failed to inject value with key ${String(key)}`
  }

  return value
}