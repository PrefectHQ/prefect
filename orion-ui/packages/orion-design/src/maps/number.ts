import { MapFunction } from '@/services/Mapper'

export const mapStringToNumber: MapFunction<string, number> = function(source: string): number {
  return parseFloat(source)
}

export const mapNumberToString: MapFunction<number, string> = function(source: number): string {
  return source.toLocaleString()
}