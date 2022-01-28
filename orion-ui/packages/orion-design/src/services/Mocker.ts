import { mocks } from '../mocks'

type Generator = (...args: any[]) => any
type GeneratorParams<T extends Generator> = Parameters<T>
type GeneratorReturns<T extends Generator> = ReturnType<T>
type OnlyRequired<T extends any[], U extends any[] = []> = Partial<T> extends T ? U : T extends [infer F, ...infer R] ? OnlyRequired<R, [...U, F]> : U
type GeneratorParamsRequired<T extends Generator> = OnlyRequired<GeneratorParams<T>>

type CreateArguments<T extends Record<string, Generator>, K extends keyof T> = GeneratorParamsRequired<T[K]> extends never[]
  ? [key: K, args?: GeneratorParams<T[K]>]
  : [key: K, args: GeneratorParams<T[K]>]

type CreateManyArguments<T extends Record<string, Generator>, K extends keyof T> = GeneratorParamsRequired<T[K]> extends never[]
  ? [key: K, count: number, args?: GeneratorParams<T[K]>]
  : [key: K, count: number, args: GeneratorParams<T[K]>]

export class Mocker<T extends Record<string, Generator>> {
  private readonly generators: T

  public constructor(generators: T) {
    this.generators = generators
  }

  public create<K extends keyof T>(...[key, args]: CreateArguments<T, K>): GeneratorReturns<T[K]> {
    const generate = this.generators[key].bind(this, ...args ?? [])

    return generate()
  }

  public createMany<K extends keyof T>(...[key, count, args]: CreateManyArguments<T, K>): GeneratorReturns<T[K]>[] {
    const generate = this.generators[key].bind(this, ...args ?? [])

    return new Array(count)
      .fill(null)
      .map(generate)
  }
}

export const mocker = new Mocker(mocks)
export type MockerFunction<T> = (this: typeof mocker, ...args: any[]) => T