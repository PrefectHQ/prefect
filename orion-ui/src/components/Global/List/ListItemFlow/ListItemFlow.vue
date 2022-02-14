<template>
  <ListItem class="list-item-flow" icon="pi-flow">
    <div class="list-item__title">
      <h2>
        {{ item.name }}
      </h2>
    </div>

    <div v-if="media.sm" class="ml-auto nowrap">
      <ButtonRounded class="mr-1" @click="filter">
        {{ flowRunCount.toLocaleString() }} flow
        {{ toPluralString('run', flowRunCount) }}
      </ButtonRounded>

      <ButtonRounded class="mr-1" @click="filter">
        {{ taskRunCount.toLocaleString() }} task
        {{ toPluralString('run', taskRunCount) }}
      </ButtonRounded>
    </div>
    <div v-if="media.md" class="list-item-flow__chart-container">
      <RunHistoryChart
        :items="flowRunHistory"
        :interval-start="start"
        :interval-end="end"
        :interval-seconds="0"
        static-median
        :padding="{ top: 3, bottom: 3, left: 3, right: 3, middle: 2 }"
        disable-popovers
      />
    </div>
  </ListItem>
</template>

<script lang="ts" setup>
import { computed } from 'vue'
import type { FlowsFilter } from '@prefecthq/orion-design'
import RunHistoryChart from '@/components/RunHistoryChart/RunHistoryChart--Chart.vue'
import { Api, Query, Endpoints } from '@/plugins/api'
import { Flow } from '@/typings/objects'
import { Buckets } from '@/typings/run_history'
import media from '@/utilities/media'
import { toPluralString } from '@/utilities/strings'
import ButtonRounded from '@/components/Global/ButtonRounded/ButtonRounded.vue'
import ListItem from '@/components/Global/List/ListItem/ListItem.vue'
import { Filter } from '@/../packages/orion-design/src/types/filters'
import { hasFilter } from '@/../packages/orion-design/src/utilities/filters'
import { useFiltersStore } from '@/../packages/orion-design/src/stores/filters'
import { FilterUrlService } from '@/../packages/orion-design/src/services/FilterUrlService'
import { useRouter } from 'vue-router'
import { FiltersQueryService } from '@/../packages/orion-design/src/services/FiltersQueryService'

const props = defineProps<{ item: Flow }>()

const filtersStore = useFiltersStore()
const router = useRouter()

const flows: FlowsFilter = {
  flows: {
    id: {
      any_: [props.item.id]
    }
  }
}

const flowRunHistoryFilter = computed(() => {
  const query = FiltersQueryService.flowHistoryQuery(filtersStore.all)

  return {
    ...query,
    history_interval_seconds: query.history_interval_seconds * 2,
    flows: flows.flows
  }
})

const start = computed<Date>(() => new Date(flowRunHistoryFilter.value.history_start))
const end = computed<Date>(() => new Date(flowRunHistoryFilter.value.history_end))

const queries: { [key: string]: Query } = {
  flow_run_history: Api.query({
    endpoint: Endpoints.flow_runs_history,
    body: flowRunHistoryFilter.value
  }),
  flow_run_count: Api.query({
    endpoint: Endpoints.flow_runs_count,
    body: flows
  }),
  task_run_count: Api.query({
    endpoint: Endpoints.task_runs_count,
    body: flows
  })
}

const flowRunCount = computed((): number => {
  return queries.flow_run_count?.response?.value || 0
})

const taskRunCount = computed((): number => {
  return queries.task_run_count?.response?.value || 0
})

const flowRunHistory = computed((): Buckets => {
  return queries.flow_run_history?.response.value || []
})

function filter() {
  const filterToAdd: Required<Filter> = {
    object: 'flow',
    property: 'name',
    type: 'string',
    operation: 'equals',
    value: props.item.name
  }
  
  if(hasFilter(filtersStore.all, filterToAdd)) {
    return
  }

  const service = new FilterUrlService(router)

  service.add(filterToAdd)
}
</script>

<style lang="scss" scoped>
.list-item-flow__chart-container {
  height: 52px;
  max-width: 175px;
}
</style>
