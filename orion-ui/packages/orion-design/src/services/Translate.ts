import { profiles } from '@/profiles'

type AnyProfile = {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  toDestination: (source: any) => any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  toSource: (destination: any) => any,
}

export class Translate<T extends Record<string, AnyProfile>> {
  private readonly profiles: T

  public constructor(profiles: T) {
    this.profiles = profiles
  }

  public toDestination<K extends keyof T>(key: K, ...[source]: Parameters<T[K]['toDestination']>): ReturnType<T[K]['toDestination']> {
    const toDestination = this.profiles[key].toDestination.bind(this, source)

    return toDestination()
  }

  public toSource<K extends keyof T>(key: K, ...[destination]: Parameters<T[K]['toSource']>): ReturnType<T[K]['toSource']> {
    const toSource = this.profiles[key].toSource.bind(this, destination)

    return toSource()
  }
}

export const translate = new Translate(profiles)

export type Profile<Source, Destination> = {
  toDestination: (source: Source) => Destination,
  toSource: (destination: Destination) => Source,
}

// todo: gotta fix (this as typeof translate).toSource()

// todo: new syntax?
// translate('IFlow:Flow').toSource(destination)
// translate('IFlow:Flow').toDestination(source)

// todo: map arrays?
// translate('IFlow[]:Flow[]').toSource(destination)

// todo: can you use ts to enforce the profile key as {source}:{destination}?