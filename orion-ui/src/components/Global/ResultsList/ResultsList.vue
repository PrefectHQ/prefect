<template>
  <List class="results-list">
    <component
      v-for="[key, item] in items"
      :key="key"
      :item="item"
      :is="props.component"
      :ref="(el) => createItemRef(key, el)"
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
  defineProps
} from 'vue'
import Observer from '@/components/Global/IntersectionObserver/IntersectionObsever.vue'
import { Api, Endpoints, FilterBody } from '@/plugins/api'

const props = defineProps<{
  filter: FilterBody
  component: string
  endpoint: string
}>()
const limit = ref(20)
const offset = ref(0)
const loading = ref(false)
const items = ref<Map<string, any>>(new Map())

const itemRefs = shallowRef<{ [key: string]: Element }>({})

const filter_ = computed(() => {
  return {
    ...props.filter,
    limit: limit.value,
    offset: offset.value
    // sort: 'EXPECTED_START_TIME_ASC'
  }
})

const getData = async () => {
  loading.value = true
  const query = Api.query({
    endpoint: Endpoints[props.endpoint],
    body: filter_.value,
    options: {}
  })
  await query.fetch()
  loading.value = false
  return query.response.value
}

const fetchMore = async () => {
  offset.value = (items.value?.size || 0) + offset.value
  const results = await getData()
  results.forEach((r: any) => {
    items.value.set(r.id, r)
  })
}

const init = async () => {
  const results = await getData()
  items.value = new Map(results.map((r: any) => [r.id, r]))
  limit.value = 10
}

init()

const isDOMElement = (el: any): boolean => el instanceof Element

const createItemRef = (id: string, el: ComponentPublicInstance): void => {
  if (!el || !el.$el || !isDOMElement(el.$el)) return
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

onMounted(() => {
  const options = {
    threshold: 0.01
  }

  observer = new IntersectionObserver(handleIntersectionObserver, options)
})

watch(
  () => props.filter,
  () => {
    offset.value = 0
    limit.value = 20
    init()
  }
)

watch(
  () => items.value,
  () => {
    if (!observer || !items.value) return
    items.value.forEach((item) => {
      if (itemRefs.value[item.id]) {
        try {
          observer.observe(itemRefs.value[item.id])
        } catch {
          // do nothing
        }
      }
    })
  }
)

onBeforeUnmount(() => {
  observer.disconnect()
})
</script>

<style lang="scss" scoped>
@use '@/styles/components/results-list.scss';

.hidden {
  visibility: hidden;
}
</style>
