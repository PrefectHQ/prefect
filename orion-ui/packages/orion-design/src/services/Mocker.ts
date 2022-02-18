import { mocks } from '@/mocks'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Mock = (...args: any[]) => any
type MockParams<T extends Mock> = Parameters<T>
type MockReturns<T extends Mock> = ReturnType<T>
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type OnlyRequired<T extends any[], U extends any[] = []> = Partial<T> extends T ? U : T extends [infer F, ...infer R] ? OnlyRequired<R, [...U, F]> : U
type MockParamsRequired<T extends Mock> = OnlyRequired<MockParams<T>>

type CreateArguments<T extends Record<string, Mock>, K extends keyof T> = MockParamsRequired<T[K]> extends never[]
  ? [key: K, args?: MockParams<T[K]>]
  : [key: K, args: MockParams<T[K]>]

type CreateManyArguments<T extends Record<string, Mock>, K extends keyof T> = MockParamsRequired<T[K]> extends never[]
  ? [key: K, count: number, args?: MockParams<T[K]>]
  : [key: K, count: number, args: MockParams<T[K]>]

export class Mocker<T extends Record<string, Mock>> {
  private readonly mockerFunctions: T

  public constructor(mockerFunctions: T) {
    this.mockerFunctions = mockerFunctions
  }

  public create<K extends keyof T>(...[key, args]: CreateArguments<T, K>): MockReturns<T[K]> {
    const mock = this.mockerFunctions[key].bind(this, ...args ?? [])

    return mock()
  }

  public createMany<K extends keyof T>(...[key, count, args]: CreateManyArguments<T, K>): MockReturns<T[K]>[] {
    const mock = this.mockerFunctions[key].bind(this, ...args ?? [])

    return new Array(count)
      .fill(null)
      .map(mock)
  }
}

export const mocker = new Mocker(mocks)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type MockFunction<T> = (this: typeof mocker, ...args: any[]) => T