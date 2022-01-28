import { MockerFunction } from '../services'

export const randomNumber: MockerFunction<number> = function(min: number = 0, max: number = 100) {
  return Math.floor(Math.random() * (max - min + 1) + min)
}