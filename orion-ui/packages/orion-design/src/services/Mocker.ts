import { mockGenerators, MockGenerator } from '../mocks'

type AnyGenerator = MockGenerator<any>
type GeneratorParams<T extends AnyGenerator> = Parameters<T>
type GeneratorReturns<T extends AnyGenerator> = ReturnType<T>
type RequiredGeneratorParams<T extends AnyGenerator> = OnlyRequired<GeneratorParams<T>>
type OnlyRequired<T extends any[], U extends any[] = []> = Partial<T> extends T ? U : T extends [infer F, ...infer R] ? OnlyRequired<R, [...U, F]> : U

export class Mocker<T extends Record<string, AnyGenerator>> {
  private readonly generators: T

  public constructor(generators: T) {
    this.generators = generators
  }

  public create<K extends keyof T>(...[key, args]: RequiredGeneratorParams<T[K]> extends never[] ? [key:K, args?: GeneratorParams<T[K]>] : [key: K, args: GeneratorParams<T[K]>]): GeneratorReturns<T[K]> {
    return this.generators[key](...args ?? [])
  }

  public createMany<K extends keyof T>(...[key, count = 3, args]: RequiredGeneratorParams<T[K]> extends never[] ? [key:K, count?: number, args?: GeneratorParams<T[K]>] : [key: K, count: number, args: GeneratorParams<T[K]>]): GeneratorReturns<T[K]>[] {
    return new Array(count)
      .fill(null)
      .map(() => this.generators[key](...args ?? []))
  }
}

export const mocker = new Mocker(mockGenerators)