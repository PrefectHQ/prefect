import { profiles, Profile } from '../profiles'

export class Mocker<T extends Profile<any>> {
  private readonly profiles: T[] = []

  public constructor(profiles: T[]) {
    this.profiles = profiles
  }

  public create<K extends T['key']>(key: K): ReturnType<Extract<T, { key: K }>['generate']> {
    const generator = this.profiles.find(x => x.key === key)

    if (!generator) {
      throw `No profile found for type ${key}`
    }

    return generator.generate()
  }

  public createMany<K extends T['key']>(key: K, count: number = 3): ReturnType<Extract<T, { key: K }>['generate']>[] {
    const results: ReturnType<Extract<T, { key: K }>['generate']>[] = []

    for (let i=0; i<count; i++) {
      results.push(this.create<K>(key))
    }

    return results
  }
}

export const mocker = new Mocker(profiles)