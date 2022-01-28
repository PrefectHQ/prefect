import { MockerFunction } from '../services'

export const randomDate: MockerFunction<Date> = function(start?: Date, end?: Date) {
  if (!start) {
    start = new Date(0)
  }

  if (!end) {
    end = new Date()
  }

  return new Date(start.getTime() + Math.random() * (end.getTime() - start.getTime()))
}