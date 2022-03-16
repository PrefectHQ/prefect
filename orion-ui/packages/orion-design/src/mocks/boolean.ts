import { MockFunction } from '@/services/Mocker'

export const randomBoolean: MockFunction<boolean> = function() {
  return Math.random() < 0.5
}