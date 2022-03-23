import { useSubscription as useSubscribeComposition } from '@prefecthq/vue-compositions'
import Subscription from '@prefecthq/vue-compositions/src/subscribe/subscription'
import { Action, SubscriptionOptions, SubscribeArguments } from '@prefecthq/vue-compositions/src/subscribe/types'

export const defaultOptions: SubscriptionOptions = { interval: 30000 }

export function useSubscription<T extends Action>(...[action, args, options, manager]: SubscribeArguments<T>): Subscription<T> {
  return useSubscribeComposition(action, args, { ...defaultOptions, ...options }, manager)
}