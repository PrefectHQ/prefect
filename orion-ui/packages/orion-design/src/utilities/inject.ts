import { inject as vueInject, InjectionKey } from 'vue'

export function requiredInject<T>(key: InjectionKey<T> | string): T {
  const injected = vueInject(key)

  if (injected === undefined) {
    throw `injection failed for key: ${String(key)}`
  }

  return injected
}