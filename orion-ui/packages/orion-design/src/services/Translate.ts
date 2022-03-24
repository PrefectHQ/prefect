import { profiles } from '@/profiles'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyProfile = Profile<any, any>
type SourceType<T extends AnyProfile> = ReturnType<T['toSource']>
type DestinationType<T extends AnyProfile> = ReturnType<T['toDestination']>

function mapToDestination<T extends AnyProfile>(profile: T, source: SourceType<T>[]): DestinationType<T>[] {
  return source.map(x => profile.toDestination(x))
}

function mapToSource<T extends AnyProfile>(profile: T, destination: DestinationType<T>[]): SourceType<T>[] {
  return destination.map(x => profile.toSource(x))
}

export function translate<K extends keyof typeof profiles>(key: K): typeof profiles[K] & {
  mapToDestination: (source: SourceType<typeof profiles[K]>[]) => DestinationType<typeof profiles[K]>[],
  mapToSource: (destination: DestinationType<typeof profiles[K]>[]) => SourceType<typeof profiles[K]>[],
} {
  const profile = profiles[key]

  return {
    ...profile,
    mapToDestination: (source: SourceType<typeof profile>[]) => mapToDestination(profile, source),
    mapToSource: (destination: DestinationType<typeof profile>[]) => mapToSource(profile, destination),
  }
}

export type Profile<Source, Destination> = {
  toDestination: (source: Source) => Destination,
  toSource: (destination: Destination) => Source,
}

// todo: map arrays?
// translate('IFlow[]:Flow[]').toSource(destination)

// todo: can you use ts to enforce the profile key as {source}:{destination}?