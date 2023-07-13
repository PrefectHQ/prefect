<template>
  <p-context-sidebar class="context-sidebar">
    <p-context-nav-item title="Dashboard" icon="ChartBarSquareIcon" :to="routes.dashboard()" />
    <p-context-nav-item title="Flow Runs" icon="FlowRun" :to="routes.flowRuns()" />
    <p-context-nav-item title="Flows" icon="Flow" :to="routes.flows()" />
    <p-context-nav-item title="Deployments" icon="MapPinIcon" :to="routes.deployments()" />
    <p-context-nav-item v-if="canSeeWorkPools" title="Work Pools" icon="CircleStackIcon" :to="routes.workPools()" />
    <p-context-nav-item v-if="!canSeeWorkPools" title="Work Queues" icon="CircleStackIcon" :to="routes.workQueues()" />
    <p-context-nav-item title="Blocks" icon="CubeIcon" :to="routes.blocks()" />
    <p-context-nav-item :title="localization.info.variables" icon="VariableIcon" :to="routes.variables()" />
    <p-context-nav-item title="Notifications" icon="BellIcon" :to="routes.notifications()" />
    <p-context-nav-item title="Task Run Concurrency" icon="Task" :to="routes.concurrencyLimits()" />
    <p-context-nav-item v-if="canSeeArtifacts" title="Artifacts" icon="FingerPrintIcon" :to="routes.artifacts()" />

    <template #footer>
      <p-context-nav-item title="Settings" icon="CogIcon" :to="routes.settings()" />
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