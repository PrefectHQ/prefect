import { Api } from '@/services/Api'

// typescript requires mixin args to have the type any[]
// https://www.typescriptlang.org/docs/handbook/mixins.html
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Constructor<T extends Api> = new (...args: any[]) => T