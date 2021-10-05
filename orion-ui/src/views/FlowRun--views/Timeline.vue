<template>
  <Card class="timeline d-flex flex-column" width="auto" shadow="sm">
    <div class="timeline-content py-2 px-2 d-flex flex-grow-1">
      <Timeline
        v-if="taskRuns.length"
        :items="taskRuns"
        :max-end-time="end"
        axis-position="top"
        background-color="blue-5"
      />
    </div>
  </Card>
</template>

<script lang="ts" setup>
import { Api, Query, Endpoints, BaseFilter } from '@/plugins/api'
import { FlowRun, TaskRun } from '@/typings/objects'
import { computed, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import Timeline from '@/components/Timeline/Timeline.vue'

const route = useRoute()

const flowRunBase: Query = await Api.query({
  endpoint: Endpoints.flow_run,
  body: {
    id: route.params.id as string
  },
  options: {
    pollInterval: 5000
  }
}).fetch()

const taskRunsFilter = computed<BaseFilter>(() => {
  return {
    flow_runs: {
      id: {
        any_: [route.params.id as string]
      }
    }
  }
})

const queries: { [key: string]: Query } = {
  task_runs: Api.query({
    endpoint: Endpoints.task_runs,
    body: taskRunsFilter,
    options: {
      pollInterval: 10000
    }
  })
}

const flowRun = computed<FlowRun>(() => {
  return flowRunBase.response?.value || {}
})

const end = computed<string>(() => {
  return flowRun.value.end_time
})
const taskRuns = computed<TaskRun[]>(() => {
  return queries.task_runs.response?.value || []
})

// This cleanup is necessary since the initial flow run query isn't
// wrapped in the queries object
onBeforeUnmount(() => {
  flowRunBase.stopPolling()
  Api.queries.delete(flowRunBase.id)
})
</script>

<style lang="scss" scoped>
@use '@/styles/views/flow-run/timeline.scss';
</style>
