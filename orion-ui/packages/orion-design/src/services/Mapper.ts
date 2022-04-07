import { maps } from '@/maps'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Map = (...args: any) => any
type Maps = Record<string, Record<string, Map>>
type MapsMember<T extends Maps, K extends keyof T> = T[K][keyof T[K]]
type Mappers<T extends Maps, K extends keyof T> = Extract<MapsMember<T, K>, Map>
type MapperSourceType<T extends Maps, K extends keyof T> = Parameters<Mappers<T, K>>[0]
type MapperDestinationType<T extends Maps, K extends keyof T> = ReturnType<Mappers<T, K>>

export class Mapper<T extends Maps> {
  private readonly mapperFunctions: T

  public constructor(mapperFunctions: T) {
    this.mapperFunctions = mapperFunctions
  }

  public map<K extends keyof T>(source: K, value: MapperSourceType<T, K>, destination: keyof T[K]): MapperDestinationType<T, K>
  public map<K extends keyof T>(source: K, value: MapperSourceType<T, K>[], destination: keyof T[K]): MapperDestinationType<T, K>[]
  public map<K extends keyof T>(source: K, value: MapperSourceType<T, K> | MapperSourceType<T, K>[], destination: keyof T[K]): MapperDestinationType<T, K> | MapperDestinationType<T, K>[] {
    const mapper = this.mapperFunctions[source][destination]

    if (Array.isArray(value)) {
      return value.map(x => this.bindMapper<K>(mapper, x))
    }

    return this.bindMapper<K>(mapper, value)
  }

  public mapEntries<K extends keyof T>(source: K, value: Record<string, MapperSourceType<T, K>>, destination: keyof T[K]): Record<string, MapperDestinationType<T, K>>
  public mapEntries<K extends keyof T>(source: K, value: Record<string, MapperSourceType<T, K>[]>, destination: keyof T[K]): Record<string, MapperDestinationType<T, K>[]>
  public mapEntries<K extends keyof T>(source: K, value: Record<string, MapperSourceType<T, K>> | Record<string, MapperSourceType<T, K>[]>, destination: keyof T[K]): Record<string, MapperDestinationType<T, K>> | Record<string, MapperDestinationType<T, K>[]> {
    const response = {} as Record<string, MapperDestinationType<T, K>>

    return Object.entries(value).reduce<Record<string, MapperDestinationType<T, K>>>((mapped, [key, value]) => {
      mapped[key] = this.map(source, value, destination)

      return mapped
    }, response)
  }

  private bindMapper<K extends keyof T>(mapper: MapsMember<T, K>, value: Parameters<MapsMember<T, K>>[0]): MapperDestinationType<T, K> {
    const map = mapper.bind(this, value)

    return map()
  }
}

export const mapper = new Mapper(maps)

export type MapFunction<Source, Destination> = (this: typeof mapper, source: Source) => Destination