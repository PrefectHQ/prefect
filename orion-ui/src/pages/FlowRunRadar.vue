<template>
  <p-layout-full class="flow-run-radar">
    <template #header>
      <PageHeadingFlowRun v-if="flowRun" :flow-run="flowRun" class="flow-run-radar__header" @delete="goToFlowRuns">
        <!-- Todo - Add this mobile scaling to Orion design -->
        <div class="flow-run-radar__header-meta">
          <StateBadge :state="flowRun.state" />
          <DurationIconText :duration="flowRun.duration" />
          <FlowIconText :flow-id="flowRun.flowId" />
        </div>
      </PageHeadingFlowRun>
    </template>

    <RadarApp :flow-run-id="flowRunId" />
  </p-layout-full>
</template>

<script lang="ts" setup>
  import {
    useRouteParam,
    RadarApp,
    PageHeadingFlowRun,
    StateBadge,
    FlowIconText,
    DurationIconText
  } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { routes } from '@/router'
  import { flowRunsApi } from '@/services/flowRunsApi'

  const router = useRouter()
  const flowRunId = useRouteParam('id')

  const options = { interval:  5000 }

  const flowRunDetailsSubscription = useSubscription(flowRunsApi.getFlowRun, [flowRunId.value], options)
  const flowRun = computed(()=> flowRunDetailsSubscription.response)

  function goToFlowRuns(): void {
    router.push(routes.flowRuns())
  }
</script>

<style>
.flow-run-radar__header-meta { @apply
  flex
  gap-2
  items-center
}
</style>