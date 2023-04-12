<template>
  <p-layout-default v-if="workPool">
    <template #header>
      <PageHeadingWorkPool :work-pool="workPool" @update="workPoolSubscription.refresh" />
    </template>

    <p-layout-well v-if="workPool" class="work-pool">
      <template #header>
        <CodeBanner :command="codeBannerCliCommand" :title="codeBannerTitle" :subtitle="codeBannerSubtitle" />
      </template>
      <p-tabs v-model:selected="tab" :tabs="tabs">
        <template #details>
          <WorkPoolDetails :work-pool="workPool" />
        </template>

        <template #runs>
          <FlowRunFilteredList :flow-run-filter="flowRunFilter" />
        </template>

        <template #work-queues>
          <WorkPoolQueuesTable :work-pool-name="workPoolName" />
        </template>

        <template #workers>
          <WorkersTable :work-pool-name="workPoolName" />
        </template>
      </p-tabs>

      <template #well>
        <WorkPoolDetails alternate :work-pool="workPool" />
      </template>
    </p-layout-well>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { media } from '@prefecthq/prefect-design'
  import { useWorkspaceApi, PageHeadingWorkPool, WorkPoolDetails, FlowRunFilteredList, WorkPoolQueuesTable, useFlowRunsFilter, useTabs, useCan, WorkersTable } from '@prefecthq/prefect-ui-library'
  import { useRouteParam, useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const api = useWorkspaceApi()
  const workPoolName = useRouteParam('workPoolName')
  const can = useCan()

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
    { label: 'Workers', hidden: !can.access.workers || isAgentWorkPool.value },
  ])

  const { tab, tabs } = useTabs(computedTabs)


  const codeBannerTitle = computed(() => {
    if (!workPool.value) {
      return 'Your work pool is ready to go!'
    }
    return `Your work pool ${workPool.value.name} is ready to go!`
  })
  const codeBannerCliCommand = computed(() => `prefect ${isAgentWorkPool.value ? 'agent' : 'worker'} start --pool ${workPool.value?.name}`)
  const codeBannerSubtitle = computed(() => `Work pools organize work that ${isAgentWorkPool.value ? 'Prefect agents' : 'Prefect workers'} can pull from.`)

  const { filter: flowRunFilter } = useFlowRunsFilter({
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