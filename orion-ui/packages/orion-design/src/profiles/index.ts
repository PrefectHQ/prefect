import { BooleanProfile } from './BooleanProfile'
import { NumberProfile } from './NumberProfile'
import { StringProfile } from './StringProfile'

export interface Profile<T> {
  readonly generate: () => T,
}

export const profiles = {
  boolean: new BooleanProfile(),
  number: new NumberProfile(),
  string: new StringProfile(),
}