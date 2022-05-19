<template>
  <div class="flow-run">
    Flow run {{ flowRunId }}
  </div>

  <div>
    {{ flowRunDetails }}
  </div>

  <div v-if="flowRunDetails?.flowId">
    <div>
      Flow Run Flow
    </div>
    {{ flowRunFlow }}
  </div>

  <div v-if="flowRunDeploymentId">
    <div>
      Flow Run Deployment
    </div>
    {{ flowRunDeployment }}
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
  import { useRouteParam, Log, LogsRequestFilter, TaskRun, FlowRunsFilter } from '@prefecthq/orion-design'
  import { PButton } from '@prefecthq/prefect-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { SubscriptionOptions } from '@prefecthq/vue-compositions/src/subscribe/types'
  import { computed, ref } from 'vue'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { flowsApi } from '@/services/flowsApi'
  import { logsApi } from '@/services/logsApi'
  import { taskRunsApi } from '@/services/taskRunsApi'

  const flowRunId = useRouteParam('id')
  const options: SubscriptionOptions = { interval:  5000 }
  const longIntervalOptions: SubscriptionOptions = { interval:  50000 }

  const flowRunDetailsSubscription = useSubscription(flowRunsApi.getFlowRun, [flowRunId.value], options)
  const flowRunDetails = computed(()=> flowRunDetailsSubscription.response)

  const flowRunFlowId = computed(()=> flowRunDetails.value?.flowId)
  const flowRunFlowSubscription = computed(() => flowRunFlowId.value ? useSubscription(flowsApi.getFlow, [flowRunFlowId.value], longIntervalOptions) : null)
  const flowRunFlow = computed(()=> flowRunFlowSubscription.value?.response)

  const flowRunDeploymentId = computed(()=> flowRunDetails.value?.deploymentId)
  const flowRunDeploymentSubscription = computed(()=> flowRunDeploymentId.value ? useSubscription(deploymentsApi.getDeployment, [flowRunDeploymentId.value], longIntervalOptions) : null)
  const flowRunDeployment = computed(()=> flowRunDeploymentSubscription.value?.response ?? 'No Deployment')

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
  const logsSort = ref<string>('TIMESTAMP_DESC')
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
      sort: logsSort.value,
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

