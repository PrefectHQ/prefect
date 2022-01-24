import { BooleanProfile } from './BooleanProfile'
import { NumberProfile } from './NumberProfile'
import { StringProfile } from './StringProfile'

export interface Profile<T> {
  readonly key: string,
  readonly generate: () => T,
}

export const profiles = [
  new BooleanProfile(),
  new NumberProfile(),
  new StringProfile(),
]