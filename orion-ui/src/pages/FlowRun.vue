<template>
  <p-layout-well class="flow-run">
    <template #header>
      <PageHeadingFlowRun v-if="flowRun" :flow-run-id="flowRun.id" @delete="goToFlowRuns" />
    </template>

    <p-tabs v-model:selected="selectedTab" :tabs="tabs">
      <template #details>
        <FlowRunDetails v-if="flowRun" :flow-run="flowRun" />
      </template>

      <template #logs>
        <FlowRunLogs v-if="flowRun" :flow-run="flowRun" />
      </template>

      <template #task-runs>
        <FlowRunTaskRuns v-if="flowRun" :flow-run-id="flowRun.id" />
      </template>

      <template #subflow-runs>
        <FlowRunSubFlows v-if="flowRun" :flow-run-id="flowRun.id" />
      </template>

      <template #parameters>
        <JsonView :value="parameters" />
      </template>
    </p-tabs>

    <template #well>
      <template v-if="flowRun">
        <FlowRunDetails :flow-run="flowRun" alternate />
      </template>
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import {
    PageHeadingFlowRun,
    FlowRunDetails,
    FlowRunLogs,
    FlowRunTaskRuns,
    FlowRunSubFlows,
    JsonView,
    useFavicon,
    useWorkspaceApi
  } from '@prefecthq/orion-design'
  import { media } from '@prefecthq/prefect-design'
  import { useSubscription, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed, ref, watch } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'

  const router = useRouter()


  const selectedTab= ref('Logs')
  const flowRunId = useRouteParam('id')
  const tabs = computed(() => {
    const values = [
      'Logs',
      'Task Runs',
      'Subflow Runs',
      'Parameters',
    ]

    if (!media.xl) {
      values.push('Details')
    }

    return values
  })

  const api = useWorkspaceApi()
  const flowRunDetailsSubscription = useSubscription(api.flowRuns.getFlowRun, [flowRunId], { interval: 30000 })
  const flowRun = computed(() => flowRunDetailsSubscription.response)

  watch(flowRunId, (oldFlowRunId, newFlowRunId) => {
    if (oldFlowRunId !== newFlowRunId) {
      selectedTab.value = 'Logs'
    }
  })

  const parameters = computed(() => {
    return flowRun.value?.parameters ? JSON.stringify(flowRun.value.parameters, undefined, 2) : '{}'
  })

  function goToFlowRuns(): void {
    router.push(routes.flowRuns())
  }

  const stateType = computed(() => flowRun.value?.stateType)
  useFavicon(stateType)

  const title = computed(() => {
    if (!flowRun.value) {
      return 'Flow Run'
    }
    return `Flow Run: ${flowRun.value.name}`
  })
  usePageTitle(title)
</script>

<style>
.flow-run__logs { @apply
  max-h-screen
}

.flow-run__header-meta { @apply
  flex
  gap-2
  items-center
  xl:hidden
}
</style>