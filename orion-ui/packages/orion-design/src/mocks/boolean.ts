import { MockGenerator } from '../mocks'

export const randomBoolean: MockGenerator<boolean> = () => {
  return Math.random() < 0.5
}