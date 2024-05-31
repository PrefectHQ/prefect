<template>
  <p-layout-well v-if="workPool" class="work-pool">
    <template #header>
      <PageHeadingWorkPool :work-pool="workPool" @update="workPoolSubscription.refresh" />
      <template v-if="showCodeBanner">
        <CodeBanner class="work-pool__code-banner" :command="codeBannerCliCommand" title="Your work pool is almost ready!" subtitle="Run this command to start." />
      </template>
    </template>
    <p-tabs v-model:selected="tab" :tabs="tabs">
      <template #details>
        <WorkPoolDetails :work-pool="workPool" />
      </template>

      <template #runs>
        <FlowRunFilteredList :filter="flowRunFilter" prefix="runs" />
      </template>

      <template #work-queues>
        <WorkPoolQueuesTable :work-pool-name="workPoolName" />
      </template>

      <template #workers>
        <WorkersTable :work-pool-name="workPoolName" />
      </template>

      <template #deployments>
        <DeploymentList :filter="deploymentsFilter" />
      </template>
    </p-tabs>

    <template #well>
      <WorkPoolDetails alternate :work-pool="workPool" />
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { media } from '@prefecthq/prefect-design'
  import {
    useWorkspaceApi,
    PageHeadingWorkPool,
    WorkPoolDetails,
    FlowRunFilteredList,
    WorkPoolQueuesTable,
    useFlowRunsFilter,
    useTabs,
    WorkersTable,
    CodeBanner,
    DeploymentList,
    useDeploymentsFilter
  } from '@prefecthq/prefect-ui-library'
  import { useRouteParam, useRouteQueryParam, useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const api = useWorkspaceApi()
  const workPoolName = useRouteParam('workPoolName')

  const subscriptionOptions = {
    interval: 300000,
  }
  const workPoolSubscription = useSubscription(api.workPools.getWorkPoolByName, [workPoolName.value], subscriptionOptions)
  const workPool = computed(() => workPoolSubscription.response)
  const isAgentWorkPool = computed(() => workPool.value?.type === 'prefect-agent')

  const computedTabs = computed(() => [
    { label: 'Details', hidden: media.xl },
    { label: 'Runs' },
    { label: 'Work Queues' },
    { label: 'Workers', hidden: isAgentWorkPool.value },
    { label: 'Deployments' },
  ])

  const tab = useRouteQueryParam('tab', 'Details')
  const { tabs } = useTabs(computedTabs, tab)

  const showCodeBanner = computed(() => workPool.value?.status !== 'ready')
  const codeBannerCliCommand = computed(() => `prefect ${isAgentWorkPool.value ? 'agent' : 'worker'} start --pool "${workPool.value?.name}"`)

  const { filter: flowRunFilter } = useFlowRunsFilter({
    workPools: {
      name: [workPoolName.value],
    },
  })

  const { filter: deploymentsFilter } = useDeploymentsFilter({
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

<style>
.work-pool__code-banner { @apply
  mt-4
}
</style>