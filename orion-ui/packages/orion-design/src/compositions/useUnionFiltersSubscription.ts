
import { useSubscription } from '@prefecthq/vue-compositions'
import { ActionArguments, ActionResponse, SubscribeArguments, UseSubscription } from '@prefecthq/vue-compositions/src/subscribe/types'
import { unrefArgs, watchableArgs } from '@prefecthq/vue-compositions/src/subscribe/utilities'
import { computed, getCurrentInstance, onUnmounted, reactive, ref, watch } from 'vue'
import { UnionFilters } from '@/services/Filter'

// any is correct here
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type UnionFiltersAction = (filters: UnionFilters) => Promise<any[]>
type UnionFiltersActionResponse<T extends UnionFiltersAction> = {
  loadMore: () => void,
} & Omit<UseSubscription<T>, 'promise'>

export function useUnionFiltersSubscription<T extends UnionFiltersAction>(...[action, args, options = {}]: SubscribeArguments<T>): UnionFiltersActionResponse<T> {
  const subscriptions = reactive<UseSubscription<T>[]>([])
  const argsWithDefault = args ?? ([] as unknown as ActionArguments<T>)
  const pages = ref(0)
  const watchable = watchableArgs(argsWithDefault)

  let unwatch: ReturnType<typeof watch> | undefined

  const loading = computed(() => subscriptions.some(subscription => subscription.loading))
  const errored = computed(() => subscriptions.some(subscription => subscription.errored))
  const error = computed(() => subscriptions.length ? subscriptions[0].error : undefined)
  const executed = computed(() => subscriptions.some(subscription => subscription.executed))

  const response = computed<ActionResponse<T>>(() => {
    const acc = [] as ActionResponse<T>

    return subscriptions.reduce((acc, subscription) => {
      const response = subscription.response ?? []

      return [...acc, ...response] as ActionResponse<T>
    }, acc)
  })

  const unsubscribe = (): void => {
    subscriptions.forEach(subscription => subscription.unsubscribe())
  }

  const refresh = (): Promise<void> => {
    return new Promise(resolve => {
      subscriptions.forEach(async (subscription) => await subscription.refresh())
      resolve()
    })
  }

  const isSubscribed = (): boolean => {
    return subscriptions.some(subscription => subscription.isSubscribed())
  }

  const loadMore = (): void => {
    const [unwrappedFilters] = unrefArgs(argsWithDefault)
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

  if (watchable !== null) {
    unwatch = watch(watchable, () => {
      if (isSubscribed()) {
        unwatch!()
        return
      }

      pages.value = 0
      unsubscribe()
      subscriptions.splice(0)

      loadMore()
    }, { deep: true })
  }

  if (getCurrentInstance()) {
    onUnmounted(() => {
      unsubscribe()

      if (unwatch) {
        unwatch()
      }
    })
  }

  return reactive({
    loading,
    executed,
    errored,
    error,
    response,
    unsubscribe,
    refresh,
    isSubscribed,
    loadMore,
  })

}