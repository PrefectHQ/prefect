<template>
  <div class="flow-run">
    Flow run {{ flowRunId }}
  </div>

  <div>
    {{ flowRunDetails }}
  </div>

  <div>
    Logs
  </div>

  <div v-for="log in logs" :key="log.id">
    {{ logs }}
  </div>

  <PButton @click="nextLogsPage">
    Next log
  </PButton>

  <div>Task Runs</div>
  <div v-for="taskRun in taskRuns" :key="taskRun.id">
    {{ taskRun }}
  </div>
  <PButton @click="nextRunPage">
    Next run
  </PButton>
</template>

<script lang="ts" setup>
  import { useRouteParam, Log, LogsRequestFilter, TaskRun, FlowRunsFilter, FlowRun } from '@prefecthq/orion-design'
  import { PButton } from '@prefecthq/prefect-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { SubscriptionOptions } from '@prefecthq/vue-compositions/src/subscribe/types'
  import { computed, ref } from 'vue'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { logsApi } from '@/services/logsApi'
  import { taskRunsApi } from '@/services/taskRunsApi'

  const flowRunId = useRouteParam('id')
  const options: SubscriptionOptions = { interval:  5000 }

  const flowRunDetailsSubscription = useSubscription(flowRunsApi.getFlowRun, [flowRunId.value], options)
  const flowRunDetails = computed(()=> flowRunDetailsSubscription.response ?? [])

  const logLevelOptions = [
    { label: 'Critical only', value: 50 },
    { label: 'Error and above', value: 40 },
    { label: 'Warning and above', value: 30 },
    { label: 'Info and above', value: 20 },
    { label: 'Debug and above', value: 10 },
    { label: 'All log levels', value: 0 },
  ] as const
  const logLevelFilter = ref<typeof logLevelOptions[number]['value']>(0)
  const logsOffset = ref<number>(0)
  const logsLimit = ref<number>(1)
  const logsFilter = computed<LogsRequestFilter>(() => {
    return {
      logs: {
        flow_run_id: {
          any_: [flowRunId.value],
        },
        level: {
          ge_: logLevelFilter.value,
        },
      },
      offset: logsOffset.value,
      limit: logsLimit.value,
      sort: 'TIMESTAMP_DESC',
    }
  })
  const logsSubscription = useSubscription(logsApi.getLogs, [logsFilter], options)
  const logs = computed<Log[]>(() => logsSubscription.response ?? [])
  // for demo only!
  const nextLogsPage = (): void => {
    logsOffset.value +=logsLimit.value
  }

  const taskRunsOffset = ref<number>(0)
  const taskRunsLimit = ref<number>(1)
  const taskRunsFilter = computed<FlowRunsFilter>(() => {
    return {
      flow_runs: {
        id: {
          any_: [flowRunId.value],
        },
      },
      offset: taskRunsOffset.value,
      limit: taskRunsLimit.value,
      sort: 'END_TIME_DESC',
    }
  })
  const subscription = useSubscription(taskRunsApi.getTaskRuns, [taskRunsFilter], options)
  const taskRuns = computed<TaskRun[]>(() => subscription.response ?? [])
  // for demo only!
  const nextRunPage = (): void => {
    taskRunsOffset.value +=logsLimit.value
  }
</script>

<style>
.flow-run {}
</style>

