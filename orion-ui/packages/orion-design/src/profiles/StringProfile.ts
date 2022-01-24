import { Profile } from '../profiles'

export class StringProfile implements Profile<string> {
  public readonly key = 'string'

  public generate(): string {
    return (Math.random() + 1).toString(36).substring(7)
  }
}