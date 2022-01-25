import { profiles, Profile } from '../profiles'

type AnyProfile = Profile<any>
type GeneratorParams<T extends AnyProfile> = Parameters<T['generate']>
type GeneratorReturns<T extends AnyProfile> = ReturnType<T['generate']>
type RequiredGeneratorParams<T extends AnyProfile> = OnlyRequired<GeneratorParams<T>>
type OnlyRequired<T extends any[], U extends any[] = []> = Partial<T> extends T ? U : T extends [infer F, ...infer R] ? OnlyRequired<R, [...U, F]> : U

export class Mocker<T extends Record<string, AnyProfile>> {
  private readonly profiles: T

  public constructor(profiles: T) {
    this.profiles = profiles
  }

  public create<K extends keyof T>(...[key, args]: RequiredGeneratorParams<T[K]> extends never[] ? [key:K, args?: GeneratorParams<T[K]>] : [key: K, args: GeneratorParams<T[K]>]): GeneratorReturns<T[K]> {
    return this.profiles[key].generate(...args ?? [])
  }

  public createMany<K extends keyof T>(...[key, count = 3, args]: RequiredGeneratorParams<T[K]> extends never[] ? [key:K, count?: number, args?: GeneratorParams<T[K]>] : [key: K, count: number, args: GeneratorParams<T[K]>]): GeneratorReturns<T[K]>[] {
    return new Array(count)
      .fill(null)
      .map(() => this.profiles[key].generate(...args ?? []))
  }
}

export const mocker = new Mocker(profiles)