<template>
  <ListItem class="list-item--flow-run" :icon="`pi-${stateType}`">
    <div class="list-item__title">
      <BreadCrumbs class="flex-grow-1" tag="h2" :crumbs="crumbs" />

      <div class="tag-container nowrap d-flex align-bottom">
        <StateLabel :name="state.name" :type="state.type" class="mr-1" />
        <m-tags :tags="tags" class="caption" />
      </div>
    </div>

    <div v-if="media.sm" class="ml-auto mr-1 nowrap">
      <ButtonRounded class="mr-1" @click="filter">
        {{ taskRunCount }} task {{ toPluralString('run', taskRunCount) }}
      </ButtonRounded>
    </div>

    <div v-if="media.md" class="chart-container mr-2">
      <RunHistoryChart
        :items="taskRunHistory"
        :interval-start="start"
        :interval-end="end"
        :interval-seconds="0"
        static-median
        :padding="{ top: 3, bottom: 3, left: 6, right: 6, middle: 2 }"
        disable-popovers
      />
    </div>
    <div class="font--secondary item--duration mr-2">
      {{ duration }}
    </div>

    <router-link :to="`/flow-run/${item.id}`" class="icon-link">
      <i class="pi pi-arrow-right-s-line" />
    </router-link>
  </ListItem>
</template>

<script lang="ts" setup>
  import { Filter, FilterUrlService, useFiltersStore, UnionFilters, FlowRunsFilter, FiltersQueryService, BreadCrumbs, Crumb, media, toPluralString, hasFilter } from '@prefecthq/orion-design'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import ButtonRounded from '@/components/Global/ButtonRounded/ButtonRounded.vue'
  import ListItem from '@/components/Global/List/ListItem/ListItem.vue'
  import StateLabel from '@/components/Global/StateLabel/StateLabel.vue'
  import RunHistoryChart from '@/components/RunHistoryChart/RunHistoryChart--Chart.vue'
  import { Api, Query, Endpoints } from '@/plugins/api'
  import { FlowRun } from '@/typings/objects'
  import { Buckets } from '@/typings/run_history'
  import { secondsToApproximateString } from '@/util/util'

  const props = defineProps<{ item: FlowRun }>()
  const filtersStore = useFiltersStore()
  const router = useRouter()

  const start = computed(() => {
    return new Date(props.item.start_time)
  })

  const end = computed(() => {
    if (!props.item.end_time) {
      const date = new Date()
      date.setMinutes(date.getMinutes() + 1)
      return date
    }

    return new Date(props.item.end_time)
  })

  const runFilter = computed(()=> FiltersQueryService.query(filtersStore.all))
  const flow_runs_filter_body: UnionFilters = {
    ...runFilter.value,
    sort: 'START_TIME_DESC',
    flow_runs: {
      ...runFilter.value.flow_runs,
      id: {
        any_: [props.item.id],
      },
    },
    task_runs: {
      ...runFilter.value.task_runs,
      subflow_runs: {
        exists_: false,
      },
    },
  }

  const flow_filter_body: FlowRunsFilter = {
    flow_runs: {
      id: {
        any_: [props.item.id],
      },
    },
  }

  const taskRunHistoryFilter = computed(() => {
    const interval = Math.floor(
      Math.max(1, (end.value.getTime() - start.value.getTime()) / 1000 / 5),
    )
    return {
      history_start: start.value.toISOString(),
      history_end: end.value.toISOString(),
      history_interval_seconds: interval,
      flow_runs: flow_runs_filter_body.flow_runs,
    }
  })

  const queries: Record<string, Query> = {
    task_run_history: Api.query({
      endpoint: Endpoints.task_runs_history,
      body: taskRunHistoryFilter.value,
    }),
    task_run_count: Api.query({
      endpoint: Endpoints.task_runs_count,
      body: flow_runs_filter_body,
    }),
    flow: Api.query({
      endpoint: Endpoints.flows,
      body: flow_filter_body,
    }),
  }

  const duration = computed(() => {
    if (props.item.state.type == 'PENDING' || props.item.state.type == 'SCHEDULED') {
      return '--'
    }

    if (props.item.total_run_time) {
      return secondsToApproximateString(props.item.total_run_time)
    }

    return secondsToApproximateString(props.item.estimated_run_time)
  })

  const state = computed(() => {
    return props.item.state
  })

  const stateType = computed(() => {
    return props.item.state.type.toLowerCase()
  })

  const tags = computed(() => {
    return props.item.tags
  })

  const flow = computed(() => {
    return queries.flow?.response?.value?.[0] || {}
  })

  const taskRunCount = computed((): number => {
    return queries.task_run_count?.response?.value || 0
  })

  const taskRunHistory = computed((): Buckets => {
    return queries.task_run_history?.response.value || []
  })

  const crumbs = computed<Crumb[]>(() => {
    return [
      { text: flow.value?.name },
      { text: props.item.name, action: `/flow-run/${props.item.id}` },
    ]
  })

  function filter(): void {
    const filterToAdd: Required<Filter> = {
      object: 'flow_run',
      property: 'name',
      type: 'string',
      operation: 'equals',
      value: props.item.name,
    }

    if (hasFilter(filtersStore.all, filterToAdd)) {
      return
    }

    const service = new FilterUrlService(router)

    service.add(filterToAdd)
  }
</script>

<style lang="scss" scoped>
@use '@/styles/components/list-item--flow-run.scss';
</style>
