<template>
  <div class="app" data-teleport-target="app">
    <template v-if="!media.lg">
      <PGlobalSidebar class="app__mobile-menu">
        <template #upper-links>
          <p-icon icon="PrefectGradient" class="app__prefect-icon" />
        </template>
        <template #bottom-links>
          <PIcon icon="MenuIcon" class="app__menu-icon" @click="toggle" />
        </template>
      </PGlobalSidebar>
    </template>
    <ContextSidebar v-if="showMenu" class="app__sidebar" @click="close" />
    <suspense>
      <AppRouterView />
    </suspense>
  </div>
</template>

<script lang="ts" setup>
  import {
    blockCatalogViewRouteKey,
    blockCatalogCreateRouteKey,
    blockCatalogRouteKey,
    blockEditRouteKey,
    blockRouteKey,
    blocksRouteKey,
    canKey,
    deploymentRouteKey,
    deploymentsRouteKey,
    editDeploymentRouteKey,
    editNotificationRouteKey,
    editQueueRouteKey,
    flowRouteKey,
    flowRunCreateRouteKey,
    flowRunRouteKey,
    flowRunsRouteKey,
    flowsRouteKey,
    notificationCreateRouteKey,
    notificationsRouteKey,
    taskRunRouteKey,
    settingsRouteKey,
    workQueueCreateRouteKey,
    workQueueRouteKey,
    workQueuesRouteKey,
    radarRouteKey
  } from '@prefecthq/orion-design'
  import { PGlobalSidebar, PIcon, media } from '@prefecthq/prefect-design'
  import { computed, provide, ref, watchEffect } from 'vue'
  import ContextSidebar from '@/components/ContextSidebar.vue'
  import AppRouterView from '@/pages/AppRouterView.vue'
  import { routes } from '@/router/routes'
  import { healthCheck } from '@/utilities/api'
  import { can } from '@/utilities/permissions'

  provide(canKey, can)

  provide(blockCatalogCreateRouteKey, routes.blocksCatalogCreate)
  provide(blockCatalogRouteKey, routes.blocksCatalog)
  provide(blockCatalogViewRouteKey, routes.blocksCatalogView)
  provide(blockEditRouteKey, routes.blockEdit)
  provide(blockRouteKey, routes.block)
  provide(blocksRouteKey, routes.blocks)
  provide(deploymentRouteKey, routes.deployment)
  provide(deploymentsRouteKey, routes.deployments)
  provide(editDeploymentRouteKey, routes.deploymentEdit)
  provide(editNotificationRouteKey, routes.notificationEdit)
  provide(editQueueRouteKey, routes.workQueueEdit)
  provide(editQueueRouteKey, routes.workQueueEdit)
  provide(flowRouteKey, routes.flow)
  provide(flowRunCreateRouteKey, routes.flowRunCreate)
  provide(flowRunRouteKey, routes.flowRun)
  provide(flowRunsRouteKey, routes.flowRuns)
  provide(flowsRouteKey, routes.flows)
  provide(notificationCreateRouteKey, routes.notificationCreate)
  provide(notificationsRouteKey, routes.notifications)
  provide(radarRouteKey, routes.radar)
  provide(settingsRouteKey, routes.settings)
  provide(taskRunRouteKey, routes.taskRun)
  provide(workQueueCreateRouteKey, routes.workQueueCreate)
  provide(workQueueCreateRouteKey, routes.workQueueCreate)
  provide(workQueueRouteKey, routes.workQueue)
  provide(workQueuesRouteKey, routes.workQueues)

  const mobileMenuOpen = ref(false)
  const showMenu = computed(() => media.lg || mobileMenuOpen.value)

  function toggle(): void {
    mobileMenuOpen.value = !mobileMenuOpen.value
  }

  function close(): void {
    mobileMenuOpen.value = false
  }

  healthCheck()

  watchEffect(() => document.body.classList.toggle('body-scrolling-disabled', showMenu.value && !media.lg))
</script>

<style>
.body-scrolling-disabled { @apply
  overflow-hidden
}

.app { @apply
  text-slate-900
}

.app {
  --prefect-scroll-margin: theme('spacing.20');
}

.app__prefect-icon { @apply
  w-6
  h-6
}

.app__menu-icon { @apply
  text-white
  w-6
  h-6
  cursor-pointer
}

@screen lg {
  .app {
    --prefect-scroll-margin: theme('spacing.2');

    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
  }
}
</style>
