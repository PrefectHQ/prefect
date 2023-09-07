<template>
  <p-context-sidebar class="context-sidebar">
    <p-context-nav-item title="Dashboard" :to="routes.dashboard()" />
    <p-context-nav-item title="Flow Runs" :to="routes.flowRuns()" />
    <p-context-nav-item title="Flows" :to="routes.flows()" />
    <p-context-nav-item title="Deployments" :to="routes.deployments()" />
    <p-context-nav-item v-if="canSeeWorkPools" title="Work Pools" :to="routes.workPools()" />
    <p-context-nav-item v-if="!canSeeWorkPools" title="Work Queues" :to="routes.workQueues()" />
    <p-context-nav-item title="Blocks" :to="routes.blocks()" />
    <p-context-nav-item :title="localization.info.variables" :to="routes.variables()" />
    <p-context-nav-item title="Notifications" :to="routes.notifications()" />
    <p-context-nav-item title="Concurrency" :to="routes.concurrencyLimits()" />
    <p-context-nav-item v-if="canSeeArtifacts" title="Artifacts" :to="routes.artifacts()" />

    <template #footer>
      <p-context-nav-item title="Settings" :to="routes.settings()" />
    </template>
  </p-context-sidebar>
</template>

<script lang="ts" setup>
  import { PContextSidebar, PContextNavItem } from '@prefecthq/prefect-design'
  import { localization } from '@prefecthq/prefect-ui-library'
  import { computed } from 'vue'
  import { useCan } from '@/compositions/useCan'
  import { routes } from '@/router'

  const can = useCan()
  const canSeeWorkPools = computed(() => can.access.work_pools && can.read.work_pool)
  const canSeeArtifacts = computed(() => can.access.artifacts)
</script>