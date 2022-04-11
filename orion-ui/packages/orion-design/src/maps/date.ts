import { MapFunction } from '@/services/Mapper'

export const mapStringToDate: MapFunction<string, Date> = function(source: string): Date {
  return new Date(source)
}

export const mapDateToString: MapFunction<Date, string> = function(source: Date): string {
  return source.toISOString()
}