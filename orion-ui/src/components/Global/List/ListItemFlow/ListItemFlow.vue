<template>
  <ListItem class="list-item-flow" icon="pi-flow">
    <div class="list-item__title">
      <h2>
        {{ item.name }}
      </h2>
    </div>

    <div v-if="media.sm" class="ml-auto nowrap">
      <ButtonRounded class="mr-1" disabled>
        {{ flowRunCount.toLocaleString() }} flow
        {{ toPluralString('run', flowRunCount) }}
      </ButtonRounded>

      <ButtonRounded class="mr-1" disabled>
        {{ taskRunCount.toLocaleString() }} task
        {{ toPluralString('run', taskRunCount) }}
      </ButtonRounded>
    </div>
    <div v-if="media.md" class="list-item-flow__chart-container">
      <RunHistoryChart
        :items="flowRunHistory"
        :interval-start="start"
        :interval-end="end"
        :interval-seconds="baseInterval * 2"
        static-median
        :padding="{ top: 3, bottom: 3, left: 3, right: 3, middle: 2 }"
        disable-popovers
      />
    </div>
  </ListItem>
</template>

<script lang="ts" setup>
import { computed } from 'vue'
import { useStore } from '@/store'
import type { FlowsFilter } from '@prefecthq/orion-design'
import RunHistoryChart from '@/components/RunHistoryChart/RunHistoryChart--Chart.vue'
import { Api, Query, Endpoints } from '@/plugins/api'
import { Flow } from '@/typings/objects'
import { Buckets } from '@/typings/run_history'
import { media, toPluralString } from '@prefecthq/orion-design/utilities'
import ButtonRounded from '@/components/Global/ButtonRounded/ButtonRounded.vue'
import ListItem from '@/components/Global/List/ListItem/ListItem.vue'

const store = useStore()
const props = defineProps<{ item: Flow }>()

const flows: FlowsFilter = {
  flows: {
    id: {
      any_: [props.item.id]
    }
  }
}

const start = computed<Date>(() => store.getters['filter/start'])
const end = computed<Date>(() => store.getters['filter/end'])
const baseInterval = computed<number>(
  () => store.getters['filter/baseInterval']
)

const flowRunHistoryFilter = computed(() => {
  return {
    history_start: start.value.toISOString(),
    history_end: end.value.toISOString(),
    history_interval_seconds: baseInterval.value * 2,
    flows: flows.flows
  }
})

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
</script>

<style lang="scss" scoped>
.list-item-flow__chart-container {
  height: 52px;
  max-width: 175px;
}
</style>
