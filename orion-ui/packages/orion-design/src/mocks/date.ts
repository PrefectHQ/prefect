import { MockGenerator } from '../mocks'

export const randomDate: MockGenerator<Date> = (start?: Date, end?: Date) => {
  if (!start) {
    start = new Date()
  }

  if (!end) {
    end = new Date(start.getTime() + 24 * 60 * 60 * 1000)
  }

  return new Date(start.getTime() + Math.random() * (end.getTime() - start.getTime()))
}