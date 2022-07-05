<template>
  <p-context-sidebar class="context-sidebar">
    <p-context-nav-item title="Flow Runs" icon="FlowRun" :to="routes.flowRuns()" />
    <p-context-nav-item title="Flows" icon="Flow" :to="routes.flows()" />
    <p-context-nav-item title="Deployments" icon="LocationMarkerIcon" :to="routes.deployments()" />
    <p-context-nav-item title="Work Queues" icon="DatabaseIcon" :to="routes.workQueues()" />
    <p-context-nav-item title="Notifications" icon="BellIcon" :to="routes.notifications()" />
    <template #footer>
      <p-context-nav-item title="Settings" icon="CogIcon" :to="routes.settings()" />
    </template>
  </p-context-sidebar>
</template>

<script lang="ts" setup>
  import { PContextSidebar, PContextNavItem } from '@prefecthq/prefect-design'
  import { routes } from '@/router'
</script>