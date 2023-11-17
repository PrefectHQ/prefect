<template>
  <p-layout-default v-if="workPoolQueue" class="work-pool-queue">
    <template #header>
      <PageHeadingWorkPoolQueue :work-pool-queue="workPoolQueue" :work-pool-name="workPoolName" @update="workPoolQueuesSubscription.refresh" />
    </template>

    <p-layout-well class="work-pool-queue__body">
      <template #header>
        <CodeBanner :command="codeBannerCliCommand" :title="codeBannerTitle" :subtitle="codeBannerSubtitle" />
      </template>

      <p-tabs v-model:selected="tab" :tabs="tabs">
        <template #details>
          <WorkPoolQueueDetails :work-pool-name="workPoolName" :work-pool-queue="workPoolQueue" />
        </template>

        <template #upcoming-runs>
          <WorkPoolQueueUpcomingFlowRunsList :work-pool-name="workPoolName" :work-pool-queue="workPoolQueue" />
        </template>

        <template #runs>
          <FlowRunFilteredList :filter="flowRunFilter" prefix="runs" />
        </template>
      </p-tabs>

      <template #well>
        <WorkPoolQueueDetails alternate :work-pool-name="workPoolName" :work-pool-queue="workPoolQueue" />
      </template>
    </p-layout-well>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { media } from '@prefecthq/prefect-design'
  import { useWorkspaceApi, PageHeadingWorkPoolQueue, CodeBanner, WorkPoolQueueDetails, WorkPoolQueueUpcomingFlowRunsList, FlowRunFilteredList, useFlowRunsFilter, useTabs } from '@prefecthq/prefect-ui-library'
  import { useRouteParam, useRouteQueryParam, useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const api = useWorkspaceApi()
  const workPoolName = useRouteParam('workPoolName')
  const workPoolNames = computed(() => [workPoolName.value])
  const workPoolQueueName = useRouteParam('workPoolQueueName')
  const workPoolQueueNames = computed(() => [workPoolQueueName.value])
  const subscriptionOptions = {
    interval: 300000,
  }

  const workPoolQueuesSubscription = useSubscription(api.workPoolQueues.getWorkPoolQueueByName, [workPoolName.value, workPoolQueueName.value], subscriptionOptions)
  const workPoolQueue = computed(() => workPoolQueuesSubscription.response)

  const workPoolSubscription = useSubscription(api.workPools.getWorkPoolByName, [workPoolName.value], subscriptionOptions)
  const workPool = computed(() => workPoolSubscription.response)
  const isAgentWorkPool = computed(() => workPool.value?.type === 'prefect-agent')

  const codeBannerTitle = computed(() => {
    if (!workPoolQueue.value) {
      return 'Your work queue is ready to go!'
    }
    return `Your work pool ${workPoolQueue.value.name} is ready to go!`
  })
  const codeBannerCliCommand = computed(() => `prefect ${isAgentWorkPool.value ? 'agent' : 'worker'} start --pool "${workPoolName.value}" --work-queue "${workPoolQueueName.value}"`)
  const codeBannerSubtitle = computed(() => `Work queues are scoped to a work pool to allow ${isAgentWorkPool.value ? 'agents' : 'workers'} to pull from groups of queues with different priorities.`)

  const { filter: flowRunFilter } = useFlowRunsFilter({
    workPoolQueues: {
      name: workPoolQueueNames,
    },
    workPools: {
      name: workPoolNames,
    },
  })

  const computedTabs = computed(() => [
    { label: 'Details', hidden: media.xl },
    { label: 'Upcoming Runs' },
    { label: 'Runs' },
  ])

  const tab = useRouteQueryParam('tab', 'Details')
  const { tabs } = useTabs(computedTabs, tab)

  const title = computed(() => {
    if (!workPoolQueueName.value) {
      return 'Work Pool Queue'
    }
    return `Work Pool Queue: ${workPoolQueueName.value}`
  })

  usePageTitle(title)
</script>

<style>
/* This is an override since this is using nested layouts */
.work-pool-queue__body {
  @apply
  p-0
}
</style>