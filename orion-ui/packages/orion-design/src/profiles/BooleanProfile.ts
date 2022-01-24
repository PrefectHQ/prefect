import { Profile } from '../profiles'

export class BooleanProfile implements Profile<boolean> {
  public readonly key = 'boolean'

  public generate(): boolean {
    return Math.random() < 0.5
  }
}