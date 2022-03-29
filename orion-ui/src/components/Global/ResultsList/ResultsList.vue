<template>
  <List class="results-list">
    <component
      :is="listComponent"
      v-for="[key, item] in items"
      :key="key"
      :ref="(el) => createItemRef(key, el as any)"
      :item="item"
    />

    <Observer @intersection="fetchMore" />
  </List>
</template>

<script lang="ts" setup>
  import {
    computed,
    ref,
    onMounted,
    onBeforeUnmount,
    watch,
    shallowRef,
    ComponentPublicInstance,
    withDefaults,
    WatchStopHandle
  } from 'vue'
  import Observer from '@/components//Global/IntersectionObserver/IntersectionObserver.vue'
  import List from '@/components/Global/List/List.vue'
  import ListItemDeployment from '@/components/Global/List/ListItemDeployment/ListItemDeployment.vue'
  import ListItemFlow from '@/components/Global/List/ListItemFlow/ListItemFlow.vue'
  import ListItemFlowRun from '@/components/Global/List/ListItemFlowRun/ListItemFlowRun.vue'
  import ListItemSubFlowRun from '@/components/Global/List/ListItemSubFlowRun/ListItemSubFlowRun.vue'
  import ListItemTaskRun from '@/components/Global/List/ListItemTaskRun/ListItemTaskRun.vue'
  import { Api, Endpoints, FilterBody, Query } from '@/plugins/api'

  const props = withDefaults(
    defineProps<{
      filter: FilterBody,
      component: 'ListItemDeployment' | 'ListItemFlow' | 'ListItemTaskRun' | 'ListItemFlowRun' | 'ListItemSubFlowRun',
      endpoint: string,
      pollInterval?: number,
    }>(),
    { pollInterval: 10000 },
  )
  const limit = ref(20)
  const offset = ref(0)
  const loading = ref(false)
  const items = ref<Map<string, any>>(new Map())

  const itemRefs = shallowRef<Record<string, Element>>({})

  const filter_ = computed(() => {
    const value: FilterBody = {
      ...props.filter,
      limit: limit.value,
      offset: offset.value,
      sort: 'EXPECTED_START_TIME_DESC',
    }

    if (props.endpoint === 'flows') {
      value.sort = 'NAME_ASC'
    }

    return value
  })

  const queries: { query: Query, watcher: WatchStopHandle }[] = []

  let watcher: WatchStopHandle

  const getData = async () => {
    if (watcher) {
      watcher()
    }

    loading.value = true

    const query = Api.query({
      endpoint: Endpoints[props.endpoint],
      body: filter_.value,
      options: {
        pollInterval: props.pollInterval,
      },
    })

    watcher = watch(query.response, (val) => {
      if (val) {
        val.forEach((r: any) => {
          items.value.set(r.id, r)
        })
      }
    })

    queries.push({ query: query, watcher: watcher })
    loading.value = false
  }

  const fetchMore = async () => {
    offset.value = (items.value?.size || 0) + offset.value
    await getData()
  }

  const init = async () => {
    await getData()
    limit.value = 10
  }

  init()

  const isDOMElement = (el: any): boolean => el instanceof Element

  const createItemRef = (id: string, el: ComponentPublicInstance): void => {
    if (!el || !el.$el || !isDOMElement(el.$el)) {
      return
    }
    itemRefs.value[id] = el.$el
  }

  let observer: IntersectionObserver

  // TODO: Figure out why #text elements are showing up in intersection observers
  const handleIntersectionObserver = (entries: IntersectionObserverEntry[]) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.remove('hidden')
      } else {
        entry.target.classList.add('hidden')
      }
    })
  }

  const listComponent = computed(() => {
    return {
      'ListItemDeployment': ListItemDeployment,
      'ListItemFlow': ListItemFlow,
      'ListItemTaskRun': ListItemTaskRun,
      'ListItemFlowRun': ListItemFlowRun,
      'ListItemSubFlowRun': ListItemSubFlowRun,
    }[props.component]
  })

  onMounted(() => {
    const options = {
      threshold: 0.01,
    }

    observer = new IntersectionObserver(handleIntersectionObserver, options)
  })

  watch(
    () => props.filter,
    () => {
      items.value.clear()
      itemRefs.value = {}
      offset.value = 0
      limit.value = 20
      init()
    },
  )

  watch(
    () => items.value,
    () => {
      if (!observer || !items.value) {
        return
      }
      items.value.forEach((item) => {
        if (itemRefs.value[item.id]) {
          try {
            observer.observe(itemRefs.value[item.id])
          } catch {
          // do nothing
          }
        }
      })
    },
  )

  onBeforeUnmount(() => {
    observer.disconnect()
    queries.forEach((queryItem) => {
      const query = Api.queries.get(queryItem.query.id)
      query?.stopPolling()

      // This removes the watcher since the query is no longer polling.
      queryItem.watcher()

      Api.queries.delete(queryItem.query.id)
    })
  })
</script>

<style lang="scss" scoped>
@use '@/styles/components/results-list.scss';

.hidden {
  visibility: hidden;
}
</style>
