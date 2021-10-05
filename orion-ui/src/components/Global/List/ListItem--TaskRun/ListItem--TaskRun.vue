<template>
  <list-item class="list-item--task-run d-flex align-start justify-start">
    <!-- For a later date... maybe -->
    <!-- :class="state + '-border'" -->

    <i
      class="item--icon pi text--grey-40 align-self-start"
      :class="`pi-${state}`"
    />
    <div
      class="
        item--title
        ml-2
        d-flex
        flex-column
        justify-center
        align-self-start
      "
    >
      <bread-crumbs class="flex-grow-1" :crumbs="crumbs" tag="h2" />

      <div class="tag-container nowrap d-flex align-bottom">
        <span
          class="run-state correct-text caption mr-1"
          :class="state + '-bg'"
        >
          {{ state }}
        </span>

        <Tag
          v-for="tag in tags"
          :key="tag"
          color="secondary-pressed"
          class="font--primary caption font-weight-semibold mr-1"
          icon="pi-label"
          flat
        >
          {{ tag }}
        </Tag>
      </div>
    </div>

    <div class="font--secondary item--duration ml-auto">
      {{ duration }}
    </div>
  </list-item>
</template>

<script lang="ts" setup>
import { defineProps, computed } from 'vue'
import { Api, Query, Endpoints, FlowRunsFilter } from '@/plugins/api'
import { TaskRun } from '@/typings/objects'
import { secondsToApproximateString } from '@/util/util'

const props = defineProps<{ item: TaskRun }>()

const flow_run_filter_body: FlowRunsFilter = {
  flow_runs: {
    id: {
      any_: [props.item.flow_run_id]
    }
  }
}

const queries: { [key: string]: Query } = {
  flow_run: Api.query({
    endpoint: Endpoints.flow_runs,
    body: flow_run_filter_body.value
  }),
  flow: Api.query({
    endpoint: Endpoints.flows,
    body: flow_run_filter_body.value
  })
}

const state = computed(() => {
  return props.item.state.type.toLowerCase()
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

const duration = computed(() => {
  return state.value == 'pending' || state.value == 'scheduled'
    ? '--'
    : props.item.total_run_time
    ? secondsToApproximateString(props.item.total_run_time)
    : secondsToApproximateString(props.item.estimated_run_time)
})

const crumbs = computed(() => {
  return [
    { text: flow.value?.name },
    { text: flowRun.value?.name, to: `/flow-run/${flowRun.value?.id}` },
    { text: props.item.name }
  ]
})
</script>

<style lang="scss" scoped>
@use '@/styles/components/list-item--task-run.scss';
</style>
