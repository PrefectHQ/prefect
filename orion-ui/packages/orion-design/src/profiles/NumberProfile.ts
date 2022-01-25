import { Profile } from '../profiles'

export class NumberProfile implements Profile<number> {
  public generate(min: number = 0, max: number = 100): number {
    return Math.floor(Math.random() * max) + min
  }
}