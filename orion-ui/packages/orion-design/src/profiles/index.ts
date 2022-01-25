import { BooleanProfile } from './BooleanProfile'
import { DateProfile } from './DateProfile'
import { NumberProfile } from './NumberProfile'
import { StringProfile } from './StringProfile'

export interface Profile<T> {
  readonly generate: (...args: any[]) => T,
}

export const profiles = {
  boolean: new BooleanProfile(),
  date: new DateProfile(),
  number: new NumberProfile(),
  string: new StringProfile(),
}