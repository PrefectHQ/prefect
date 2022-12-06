<template>
  <p-layout-full class="flow-run-radar">
    <template #header>
      <PageHeadingFlowRunRadar v-if="flowRun" :flow-run="flowRun" class="flow-run-radar__header" @delete="goToFlowRuns" />
    </template>

    <RadarApp :flow-run-id="flowRunId" />
  </p-layout-full>
</template>

<script lang="ts" setup>
  import { RadarApp, PageHeadingFlowRunRadar, useWorkspaceApi } from '@prefecthq/orion-design'
  import { useSubscription, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'

  const router = useRouter()
  const flowRunId = useRouteParam('flowRunId')

  const options = { interval:  5000 }

  const api = useWorkspaceApi()
  const flowRunDetailsSubscription = useSubscription(api.flowRuns.getFlowRun, [flowRunId.value], options)
  const flowRun = computed(() => flowRunDetailsSubscription.response)

  function goToFlowRuns(): void {
    router.push(routes.flowRuns())
  }

  const title = computed<string | null>(() => {
    if (!flowRun.value) {
      return 'Radar View for Flow Run'
    }
    return `Radar View for Flow Run: ${flowRun.value.name}`
  })
  usePageTitle(title)
</script>

<style>
.flow-run-radar__header-meta { @apply
  flex
  gap-2
  items-center
}
</style>