<template>
  <ResultsListBase @load-more="fetchMore">
    <list class="results-list">
      <component
        v-for="item in items"
        :key="item.id"
        :item="item"
        :is="props.component"
      />
    </list>
  </ResultsListBase>
</template>

<script lang="ts" setup>
import { computed, ref } from 'vue'
import ResultsListBase from './ResultsList--Base.vue'
import { Api, Endpoints, FilterBody } from '@/plugins/api'

const props = defineProps<{
  filter: FilterBody
  component: string
  endpoint: string
}>()
const limit = ref(25)
const offset = ref(0)
const loading = ref(false)
const items = ref<any[]>([])

const filter_ = computed(() => {
  return { ...props.filter, limit: limit.value, offset: offset.value }
})

const getData = async () => {
  loading.value = true
  const query = Api.query(Endpoints[props.endpoint], filter_.value, {})
  await query.fetch()
  loading.value = false
  return query.response.value
}

const fetchMore = async () => {
  offset.value = items.value.length + limit.value
  const results = await getData()
  items.value = [...items.value, ...results]
}

const init = async () => {
  items.value = await getData()
  limit.value = 5
}

init()
</script>

<style lang="scss" scoped>
@use '@/styles/components/results-list.scss';
</style>
