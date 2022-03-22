
import { useSubscription } from '@prefecthq/vue-compositions'
import Subscription from '@prefecthq/vue-compositions/src/subscribe/subscription'
import { ActionArguments, ActionResponse, SubscriptionOptions } from '@prefecthq/vue-compositions/src/subscribe/types'
import { unrefArgs, watchableArgs } from '@prefecthq/vue-compositions/src/subscribe/utilities'
import { computed, isReactive, isRef, reactive, ref, unref, watch } from 'vue'
import { UnionFilters } from '@/services/Filter'

type UnionFiltersAction = (filters: UnionFilters) => any[] | Promise<any[]>
type UnionFiltersActionResponse<T extends UnionFiltersAction> = {
  loadMore: () => void,
  response: ActionResponse<T>,
}

export function useSubscriptionWithPaging<T extends UnionFiltersAction>(
  action: T,
  args: ActionArguments<T>,
  options: SubscriptionOptions = {},
): UnionFiltersActionResponse<T> {
  const subscriptions = reactive<Subscription<T>[]>([])
  const pages = ref(0)

  const response = computed<ActionResponse<T>>(() => {
    const acc = [] as ActionResponse<T>

    return subscriptions.reduce((acc, subscription) => {
      const response = (subscription.response as any).value ?? []

      return [...acc, ...response] as ActionResponse<T>
    }, acc)
  })

  const loadMore = (): void => {
    const [unwrappedFilters] = unrefArgs(args)
    const limit = unwrappedFilters.limit ?? 200

    if (subscriptions.length * limit > response.value.length) {
      return
    }

    const offset = (unwrappedFilters.offset ?? limit) * pages.value
    const subscriptionFilters = [{ ...unwrappedFilters, offset, limit }] as Parameters<T>
    const subscription = useSubscription<T>(action, subscriptionFilters, options)

    subscriptions.push(reactive(subscription))

    pages.value++
  }

  if (
    isRef(args) ||
    isReactive(args) ||
    (unref(args) as Parameters<T>).some(isRef) ||
    (unref(args) as Parameters<T>).some(isReactive)
  ) {
    const argsToWatch = watchableArgs(args)

    watch(argsToWatch, () => {
      pages.value = 1
      subscriptions.splice(0)

      loadMore()
    })
  }

  return reactive({
    response,
    loadMore,
  })

}