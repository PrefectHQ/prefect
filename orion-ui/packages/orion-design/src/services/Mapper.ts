import { maps } from '@/maps'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Map = (...args: any) => any
type Maps = Record<string, Record<string, Map>>
type MapsMember<T extends Maps, SOURCE extends keyof T> = T[SOURCE][keyof T[SOURCE]]
type Mappers<T extends Maps, SOURCE extends keyof T> = Extract<MapsMember<T, SOURCE>, Map>
type MapperSourceType<T extends Maps, SOURCE extends keyof T> = Parameters<Mappers<T, SOURCE>>[0]
type MapperDestinationType<T extends Maps, SOURCE extends keyof T, DESTINATION extends keyof T[SOURCE]> = ReturnType<T[SOURCE][DESTINATION]>

export class Mapper<T extends Maps> {
  private readonly mapperFunctions: T

  public constructor(mapperFunctions: T) {
    this.mapperFunctions = mapperFunctions
  }

  public map<SOURCE extends keyof T, DESTINATION extends keyof T[SOURCE]>(source: SOURCE, value: MapperSourceType<T, SOURCE>, destination: DESTINATION): MapperDestinationType<T, SOURCE, DESTINATION>
  public map<SOURCE extends keyof T, DESTINATION extends keyof T[SOURCE]>(source: SOURCE, value: MapperSourceType<T, SOURCE> | null, destination: DESTINATION): MapperDestinationType<T, SOURCE, DESTINATION> | null
  public map<SOURCE extends keyof T, DESTINATION extends keyof T[SOURCE]>(source: SOURCE, value: MapperSourceType<T, SOURCE>[], destination: DESTINATION): MapperDestinationType<T, SOURCE, DESTINATION>[]
  public map<SOURCE extends keyof T, DESTINATION extends keyof T[SOURCE]>(source: SOURCE, value: MapperSourceType<T, SOURCE> | MapperSourceType<T, SOURCE>[] | null, destination: DESTINATION): MapperDestinationType<T, SOURCE, DESTINATION> | MapperDestinationType<T, SOURCE, DESTINATION>[] | null {
    if (value === null) {
      return null
    }

    const mapper = this.mapperFunctions[source][destination]

    if (Array.isArray(value)) {
      return value.map(x => this.bindMapper<SOURCE, DESTINATION>(mapper, x))
    }

    return this.bindMapper<SOURCE, DESTINATION>(mapper, value)
  }

  public mapEntries<SOURCE extends keyof T, DESTINATION extends keyof T[SOURCE]>(source: SOURCE, value: Record<string, MapperSourceType<T, SOURCE>>, destination: DESTINATION): Record<string, MapperDestinationType<T, SOURCE, DESTINATION>>
  public mapEntries<SOURCE extends keyof T, DESTINATION extends keyof T[SOURCE]>(source: SOURCE, value: Record<string, MapperSourceType<T, SOURCE> | null>, destination: DESTINATION): Record<string, MapperDestinationType<T, SOURCE, DESTINATION> | null>
  public mapEntries<SOURCE extends keyof T, DESTINATION extends keyof T[SOURCE]>(source: SOURCE, value: Record<string, MapperSourceType<T, SOURCE>[]>, destination: DESTINATION): Record<string, MapperDestinationType<T, SOURCE, DESTINATION>[]>
  public mapEntries<SOURCE extends keyof T, DESTINATION extends keyof T[SOURCE]>(source: SOURCE, value: Record<string, MapperSourceType<T, SOURCE> | MapperSourceType<T, SOURCE>[] | null> | Record<string, MapperSourceType<T, SOURCE>>, destination: DESTINATION): Record<string, MapperDestinationType<T, SOURCE, DESTINATION> | MapperDestinationType<T, SOURCE, DESTINATION>[] | null> {
    const response = {} as Record<string, MapperDestinationType<T, SOURCE, DESTINATION>>

    return Object.entries(value).reduce<Record<string, MapperDestinationType<T, SOURCE, DESTINATION>>>((mapped, [key, value]) => {
      mapped[key] = this.map(source, value, destination)

      return mapped
    }, response)
  }

  private bindMapper<SOURCE extends keyof T, DESTINATION extends keyof T[SOURCE]>(mapper: MapsMember<T, SOURCE>, value: Parameters<MapsMember<T, SOURCE>>[0]): MapperDestinationType<T, SOURCE, DESTINATION> {
    const map = mapper.bind(this, value)

    return map()
  }
}

export const mapper = new Mapper(maps)

export type MapFunction<SOURCE, DESTINATION> = (this: typeof mapper, source: SOURCE) => DESTINATION