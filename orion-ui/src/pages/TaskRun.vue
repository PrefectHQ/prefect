<template>
  <p-layout-well class="task-run">
    <template #header>
      <PageHeadingTaskRun v-if="taskRun" :task-run="taskRun" @delete="goToFlowRun" />
    </template>

    <p-tabs :tabs="tabs">
      <template #details>
        <TaskRunDetails v-if="taskRun" :task-run="taskRun" />
      </template>

      <template #logs>
        <TaskRunLogs v-if="taskRun" :task-run="taskRun" />
      </template>

      <template #task-inputs>
        <JsonView v-if="taskRun" :value="parameters" />
      </template>
    </p-tabs>
    <template #well>
      <template v-if="taskRun">
        <div class="task-run__meta">
          <StateBadge :state="taskRun.state" />
          <DurationIconText :duration="taskRun.duration" />
          <FlowRunIconText :flow-run-id="taskRun.flowRunId" />
        </div>

        <p-divider />

        <!-- <TaskRunDetails alternate :task-run="taskRun" /> -->
      </template>
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { PageHeadingTaskRun, TaskRunLogs, TaskRunDetails, StateBadge, DurationIconText, FlowRunIconText, JsonView } from '@prefecthq/orion-design'
  import { media } from '@prefecthq/prefect-design'
  import { useSubscription, useRouteParam } from '@prefecthq/vue-compositions'
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

  const taskRunDetailsSubscription = useSubscription(taskRunsApi.getTaskRun, [taskRunId], { interval: 5000 })
  const taskRun = computed(() => taskRunDetailsSubscription.response)
  const flowRunId = computed(() => taskRun.value?.flowRunId)

  const flowRunDetailsSubscription = useSubscription(flowRunsApi.getFlowRun, [flowRunId.value!], { interval: 5000 })

  const parameters = computed(() => {
    return taskRun.value?.taskInputs ? JSON.stringify(taskRun.value.taskInputs, undefined, 2) : '{}'
  })

  function goToFlowRun(): void {
    flowRunDetailsSubscription.refresh()
    router.push(routes.flowRun(flowRunId.value!))
  }
</script>

<style>
.task-run__meta { @apply
  flex
  flex-col
  gap-2
  items-start
}
</style>