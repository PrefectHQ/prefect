<template>
  <p-layout-well class="flow-run">
    <template #header>
      <PageHeadingFlowRun v-if="flowRun" :flow-run="flowRun" @delete="goToFlowRuns" />
    </template>

    <p-tabs :tabs="tabs">
      <template #details>
        <router-link :to="routes.radar(flowRunId)" class="flow-run__small-radar-link">
          <RadarSmall :flow-run-id="flowRunId" class="flow-run__small-radar" />
        </router-link>

        <p-divider />

        <FlowRunDetails v-if="flowRun" :flow-run="flowRun" />
      </template>

      <template #logs>
        <FlowRunLogs v-if="flowRun" :flow-run="flowRun" />
      </template>

      <template #task-runs>
        <FlowRunTaskRuns v-if="flowRun" :flow-run-id="flowRun.id" />
      </template>

      <template #sub-flow-runs>
        <FlowRunSubFlows v-if="flowRun" :flow-run-id="flowRun.id" />
      </template>

      <template #parameters>
        <JsonView :value="parameters" />
      </template>
    </p-tabs>

    <template #well>
      <template v-if="flowRun">
        <div class="flow-run__meta">
          <StateBadge :state="flowRun.state" />
          <DurationIconText :duration="flowRun.duration" />
          <FlowIconText :flow-id="flowRun.flowId" />
          <DeploymentIconText v-if="flowRun.deploymentId" :deployment-id="flowRun.deploymentId" />
          <FlowRunStartTime :flow-run="flowRun" />
        </div>

        <p-divider />

        <router-link :to="routes.radar(flowRunId)" class="flow-run__small-radar-link">
          <RadarSmall :flow-run-id="flowRunId" class="flow-run__small-radar" />
        </router-link>

        <p-divider />

        <FlowRunDetails :flow-run="flowRun" alternate />
      </template>
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import {
    PageHeadingFlowRun,
    FlowRunDetails,
    RadarSmall,
    StateBadge,
    FlowIconText,
    DeploymentIconText,
    DurationIconText,
    FlowRunLogs,
    FlowRunTaskRuns,
    FlowRunStartTime,
    FlowRunSubFlows,
    JsonView,
    useFavicon
  } from '@prefecthq/orion-design'
  import { PDivider, media } from '@prefecthq/prefect-design'
  import { useSubscription, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'
  import { flowRunsApi } from '@/services/flowRunsApi'

  const router = useRouter()
  const flowRunId = useRouteParam('id')

  const tabs = computed(() => {
    const values = ['Logs', 'Task Runs', 'Sub Flow Runs', 'Parameters']

    if (!media.xl) {
      values.push('Details')
    }

    return values
  })

  const flowRunDetailsSubscription = useSubscription(flowRunsApi.getFlowRun, [flowRunId], { interval: 5000 })
  const flowRun = computed(() => flowRunDetailsSubscription.response)

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

.flow-run__meta { @apply
  flex
  flex-col
  gap-2
  items-start
}

.flow-run__small-radar { @apply
  h-[250px]
  w-[250px]
}

.flow-run__small-radar-link { @apply
  cursor-pointer
  inline-block
}
</style>