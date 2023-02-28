<template>
  <p-layout-well v-if="workPool" class="work-pool">
    <template #header>
      <PageHeadingWorkPool :work-pool="workPool" @update="workPoolSubscription.refresh" />
    </template>

    <p-tabs :tabs="tabs">
      <template #details>
        <WorkPoolDetails :work-pool="workPool" />
      </template>

      <template #runs>
        <FlowRunFilteredList :flow-run-filter="flowRunFilter" />
      </template>

      <template #work-queues>
        <WorkPoolQueuesTable :work-pool-name="workPoolName" />
      </template>
    </p-tabs>

    <template #well>
      <WorkPoolDetails alternate :work-pool="workPool" />
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { media } from '@prefecthq/prefect-design'
  import { useWorkspaceApi, PageHeadingWorkPool, WorkPoolDetails, FlowRunFilteredList, WorkPoolQueuesTable, useRecentFlowRunsFilter } from '@prefecthq/prefect-ui-library'
  import { useRouteParam, useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const api = useWorkspaceApi()
  const workPoolName = useRouteParam('workPoolName')

  const tabs = computed(() => {
    const values = ['Runs', 'Work Queues']

    if (!media.xl) {
      values.unshift('Details')
    }

    return values
  })

  const subscriptionOptions = {
    interval: 300000,
  }
  const workPoolSubscription = useSubscription(api.workPools.getWorkPoolByName, [workPoolName.value], subscriptionOptions)
  const workPool = computed(() => workPoolSubscription.response)

  const { filter: flowRunFilter } = useRecentFlowRunsFilter({
    workPools: {
      name: [workPoolName.value],
    },
  })

  const title = computed(() => {
    if (!workPool.value) {
      return 'Work Pool'
    }
    return `Work Pool: ${workPool.value.name}`
  })

  usePageTitle(title)
</script>