import { MockFunction } from '@/services/Mocker'

export const randomNumber: MockFunction<number> = function(min: number = 0, max: number = 100) {
  return Math.floor(Math.random() * (max - min + 1) + min)
}