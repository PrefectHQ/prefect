import { Profile } from '@/services/Translate'

export const dateProfile: Profile<string, Date> = {
  toDestination(source) {
    return new Date(source)
  },
  toSource(destination) {
    return destination.toISOString()
  },
}