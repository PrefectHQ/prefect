<template>
  <ListItem class="list-item--flow-run" :icon="`pi-${state}`">
    <div class="list-item__title">
      <BreadCrumbs class="flex-grow-1" tag="h2" :crumbs="crumbs" />

      <div class="tag-container nowrap d-flex">
        <StateLabel :name="state.name" :type="state.type" class="mr-1" />
        <m-tags :tags="tags" class="caption" />
      </div>
    </div>

    <div v-if="media.sm" class="ml-auto mr-1 nowrap">
      <ButtonRounded class="mr-1" disabled>
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
  import { BreadCrumbs, Crumb, FlowRunsFilter, media, toPluralString } from '@prefecthq/orion-design'
  import { computed } from 'vue'
  import StateLabel from '@/components/Global/StateLabel/StateLabel.vue'
  import RunHistoryChart from '@/components/RunHistoryChart/RunHistoryChart--Chart.vue'
  import { Api, Query, Endpoints } from '@/plugins/api'
  import { TaskRun } from '@/typings/objects'
  import { Buckets } from '@/typings/run_history'
  import { secondsToApproximateString } from '@/util/util'

  const props = defineProps<{ item: TaskRun }>()

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

  const flowRunFilterBody = computed<FlowRunsFilter>(() => {
    return {
      flow_runs: {
        id: {
          any_: [props.item.state.state_details.child_flow_run_id],
        },
      },
    }
  })

  const taskRunHistoryFilter = computed(() => {
    const interval = Math.floor(
      Math.max(1, (end.value.getTime() - start.value.getTime()) / 1000 / 5),
    )
    return {
      history_start: start.value.toISOString(),
      history_end: end.value.toISOString(),
      history_interval_seconds: interval,
      flow_runs: flowRunFilterBody.value.flow_runs,
    }
  })

  const queries: Record<string, Query> = {
    flow_run: Api.query({
      endpoint: Endpoints.flow_runs,
      body: flowRunFilterBody.value,
    }),
    flow: Api.query({
      endpoint: Endpoints.flows,
      body: flowRunFilterBody.value,
    }),
    task_run_history: Api.query({
      endpoint: Endpoints.task_runs_history,
      body: taskRunHistoryFilter.value,
    }),
    task_run_count: Api.query({
      endpoint: Endpoints.task_runs_count,
      body: flowRunFilterBody,
    }),
  }

  const state = computed(() => {
    return props.item.state
  })

  const tags = computed(() => {
    return props.item.tags
  })

  const flowRun = computed(() => {
    return queries.flow_run?.response?.value?.[0] || {}
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

  const duration = computed(() => {
    if (props.item.state.type == 'PENDING' || props.item.state.type == 'SCHEDULED') {
      return '--'
    }

    if (props.item.total_run_time) {
      return secondsToApproximateString(props.item.total_run_time)
    }

    return secondsToApproximateString(props.item.estimated_run_time)
  })

  const crumbs = computed<Crumb[]>(() => {
    return [
      { text: flow.value?.name },
      { text: flowRun.value?.name, action: `/flow-run/${flowRun.value?.id}` },
      { text: props.item.name },
    ]
  })
</script>

<style lang="scss" scoped>
@use '@/styles/components/list-item--flow-run.scss';
</style>
