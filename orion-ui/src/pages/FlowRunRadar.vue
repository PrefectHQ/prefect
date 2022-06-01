<template>
  <p-layout-full class="flow-run">
    <template #header>
      <PageHeadingFlowRun v-if="flowRun" :flow-run="flowRun" @delete="goToFlowRuns">
        <div class="flow-run__header-meta">
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
.flow-run__filters { @apply
  flex
  gap-1
  items-center
  justify-end
  mb-2
}

.flow-run__logs {
  min-height: 500px;
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
  gap-3
  items-start
}
</style>