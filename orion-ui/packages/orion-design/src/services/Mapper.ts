import { maps } from '@/maps'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Map = (...args: any) => any
type Maps = Record<string, Record<string, Map>>
type MapsMember<T extends Maps, S extends keyof T> = T[S][keyof T[S]]
type Mappers<T extends Maps, S extends keyof T> = Extract<MapsMember<T, S>, Map>
type MapperSourceType<T extends Maps, S extends keyof T> = Parameters<Mappers<T, S>>[0]
type MapperDestinationType<T extends Maps, S extends keyof T, D extends keyof T[S]> = ReturnType<T[S][D]>

export class Mapper<T extends Maps> {
  private readonly mapperFunctions: T

  public constructor(mapperFunctions: T) {
    this.mapperFunctions = mapperFunctions
  }

  public map<S extends keyof T, D extends keyof T[S]>(source: S, value: MapperSourceType<T, S>, destination: D): MapperDestinationType<T, S, D>
  public map<S extends keyof T, D extends keyof T[S]>(source: S, value: MapperSourceType<T, S> | null | undefined, destination: D): MapperDestinationType<T, S, D> | null | undefined
  public map<S extends keyof T, D extends keyof T[S]>(source: S, value: MapperSourceType<T, S>[], destination: D): MapperDestinationType<T, S, D>[]
  public map<S extends keyof T, D extends keyof T[S]>(source: S, value: MapperSourceType<T, S> | MapperSourceType<T, S>[] | null | undefined, destination: D): MapperDestinationType<T, S, D> | MapperDestinationType<T, S, D>[] | null | undefined {
    if (value === null || value === undefined) {
      return value
    }

    const mapper = this.bindMapper(this.mapperFunctions[source][destination])

    if (Array.isArray(value)) {
      return value.map(mapper)
    }

    return mapper(value)
  }

  public mapEntries<S extends keyof T, D extends keyof T[S]>(source: S, value: Record<string, MapperSourceType<T, S>>, destination: D): Record<string, MapperDestinationType<T, S, D>>
  public mapEntries<S extends keyof T, D extends keyof T[S]>(source: S, value: Record<string, MapperSourceType<T, S>> | null | undefined, destination: D): Record<string, MapperDestinationType<T, S, D>> | null | undefined
  public mapEntries<S extends keyof T, D extends keyof T[S]>(source: S, value: Record<string, MapperSourceType<T, S>[]>, destination: D): Record<string, MapperDestinationType<T, S, D>[]>
  public mapEntries<S extends keyof T, D extends keyof T[S]>(source: S, value: Record<string, MapperSourceType<T, S>[]> | null | undefined, destination: D): Record<string, MapperDestinationType<T, S, D>[]> | null | undefined
  public mapEntries<S extends keyof T, D extends keyof T[S]>(source: S, value: Record<string, MapperSourceType<T, S> | MapperSourceType<T, S>[]> | null | undefined, destination: D): Record<string, MapperDestinationType<T, S, D> | MapperDestinationType<T, S, D>[]> | null | undefined {
    if (value === null || value === undefined) {
      return value
    }

    const response = {} as Record<string, MapperDestinationType<T, S, D>>

    return Object.entries(value).reduce<Record<string, MapperDestinationType<T, S, D>>>((mapped, [key, value]) => {
      mapped[key] = this.map(source, value, destination)

      return mapped
    }, response)
  }

  private bindMapper<S extends keyof T, D extends keyof T[S]>(mapper: MapsMember<T, S>): (source: MapperSourceType<T, S>) => MapperDestinationType<T, S, D> {
    return mapper.bind(this)
  }
}

export const mapper = new Mapper(maps)

export type MapFunction<S, D> = (this: typeof mapper, source: S) => D