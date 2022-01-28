import { MockerFunction } from '../services'

export const randomBoolean: MockerFunction<boolean> = function() {
  return Math.random() < 0.5
}