import { Profile } from '../profiles'

export class NumberProfile implements Profile<number> {
  public readonly key = 'number'

  public generate(): number {
    return Math.floor(Math.random() * 101)
  }
}