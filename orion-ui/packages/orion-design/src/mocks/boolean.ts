import { MockFunction } from '../services'

export const randomBoolean: MockFunction<boolean> = function() {
  return Math.random() < 0.5
}