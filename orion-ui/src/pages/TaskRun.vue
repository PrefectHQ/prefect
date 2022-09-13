<template>
  <p-layout-well v-if="taskRun" class="task-run">
    <template #header>
      <PageHeadingTaskRun :task-run="taskRun" @delete="goToFlowRun" />
    </template>

    <p-tabs :tabs="tabs">
      <template #details>
        <TaskRunDetails :task-run="taskRun" />
      </template>

      <template #logs>
        <TaskRunLogs :task-run="taskRun" />
      </template>

      <template #task-inputs>
        <JsonView :value="parameters" />
      </template>
    </p-tabs>
    <template #well>
      <div class="task-run__meta">
        <StateBadge :state="taskRun.state" />
        <DurationIconText :duration="taskRun.duration" />
        <FlowRunIconText :flow-run-id="taskRun.flowRunId" />
      </div>

      <p-divider />

      <TaskRunDetails alternate :task-run="taskRun" />
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { PageHeadingTaskRun, TaskRunLogs, TaskRunDetails, StateBadge, DurationIconText, FlowRunIconText, JsonView, useFavicon } from '@prefecthq/orion-design'
  import { media } from '@prefecthq/prefect-design'
  import { useRouteParam, useSubscriptionWithDependencies } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { routes } from '@/router'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { taskRunsApi } from '@/services/taskRunsApi'

  const router = useRouter()
  const taskRunId = useRouteParam('id')

  const tabs = computed(() => {
    const values = ['Logs', 'Task Inputs']

    if (!media.xl) {
      values.push('Details')
    }

    return values
  })


  const taskRunIdArgs = computed<[string] | null>(() => taskRunId.value ? [taskRunId.value] : null)
  const taskRunDetailsSubscription = useSubscriptionWithDependencies(taskRunsApi.getTaskRun, taskRunIdArgs)
  const taskRun = computed(() => taskRunDetailsSubscription.response)

  const flowRunId = computed(() => taskRun.value?.flowRunId)
  const flowRunIdArgs = computed<[string] | null>(() => flowRunId.value ? [flowRunId.value] : null)
  const flowRunDetailsSubscription = useSubscriptionWithDependencies(flowRunsApi.getFlowRun, flowRunIdArgs)

  const parameters = computed(() => {
    return taskRun.value?.taskInputs ? JSON.stringify(taskRun.value.taskInputs, undefined, 2) : '{}'
  })

  function goToFlowRun(): void {
    flowRunDetailsSubscription.refresh()
    router.push(routes.flowRun(flowRunId.value!))
  }

  const stateType = computed(() => taskRun.value?.stateType)
  useFavicon(stateType)
</script>

<style>
.task-run__meta { @apply
  flex
  flex-col
  gap-2
  items-start
}
</style>