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
        <FlowRunTaskRuns v-if="flowRun" :flow-run="flowRun" />
      </template>

      <template #sub-flow-runs>
        <FlowRunSubFlows v-if="flowRun" :flow-run="flowRun" />
      </template>
    </p-tabs>

    <template #well>
      <template v-if="flowRun">
        <div class="flow-run__meta">
          <StateBadge :state="flowRun.state" />
          <DurationIconText :duration="flowRun.duration" />
          <FlowIconText :flow-id="flowRun.flowId" />
          <DeploymentIconText v-if="flowRun.deploymentId" :deployment-id="flowRun.deploymentId" />
        </div>

        <p-divider />

        <router-link :to="routes.radar(flowRunId)" class="flow-run__small-radar-link">
          <RadarSmall :flow-run-id="flowRunId" class="flow-run__small-radar" />
        </router-link>

        <p-divider />

        <FlowRunDetails :flow-run="flowRun" />
      </template>
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import {
    useRouteParam,
    PageHeadingFlowRun,
    FlowRunDetails,
    RadarSmall,
    StateBadge,
    FlowIconText,
    DeploymentIconText,
    DurationIconText,
    FlowRunLogs,
    FlowRunTaskRuns,
    FlowRunSubFlows
  } from '@prefecthq/orion-design'
  import { PDivider, media } from '@prefecthq/prefect-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { routes } from '@/router'
  import { flowRunsApi } from '@/services/flowRunsApi'

  const router = useRouter()
  const flowRunId = useRouteParam('id')

  const tabs = computed(() => {
    const values = ['Logs', 'Task Runs', 'Sub Flow Runs']

    if (!media.xl) {
      values.push('Details')
    }

    return values
  })

  const flowRunDetailsSubscription = useSubscription(flowRunsApi.getFlowRun, [flowRunId.value], { interval: 5000 })
  const flowRun = computed(() => flowRunDetailsSubscription.response)

  function goToFlowRuns(): void {
    router.push(routes.flowRuns())
  }
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