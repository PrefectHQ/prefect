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
    blockCapabilitiesApiKey,
    blockCatalogViewRouteKey,
    blockCatalogCreateRouteKey,
    blockCatalogRouteKey,
    blockDocumentsApiKey,
    blockEditRouteKey,
    blockRouteKey,
    blockSchemasApiKey,
    blocksRouteKey,
    blockTypesApiKey,
    canKey,
    deploymentRouteKey,
    deploymentsApiKey,
    deploymentsRouteKey,
    editDeploymentRouteKey,
    editNotificationRouteKey,
    editQueueRouteKey,
    flowRouteKey,
    flowRunCreateRouteKey,
    flowRunRouteKey,
    flowRunsApiKey,
    flowRunsRouteKey,
    flowsApiKey,
    flowsRouteKey,
    logsApiKey,
    notificationCreateRouteKey,
    notificationsApiKey,
    notificationsRouteKey,
    taskRunRouteKey,
    settingsRouteKey,
    taskRunsApiKey,
    workQueueCreateRouteKey,
    workQueueRouteKey,
    workQueuesApiKey,
    workQueuesRouteKey
  } from '@prefecthq/orion-design'
  import { PGlobalSidebar, PIcon, media } from '@prefecthq/prefect-design'
  import { computed, provide, ref, watchEffect } from 'vue'
  import { blockDocumentsApi } from './services/blockDocumentsApi'
  import { blockSchemasApi } from './services/blockSchemasApi'
  import { blockTypesApi } from './services/blockTypesApi'
  import { notificationsApi } from './services/notificationsApi'
  import ContextSidebar from '@/components/ContextSidebar.vue'
  import AppRouterView from '@/pages/AppRouterView.vue'
  import { routes } from '@/router/routes'
  import { blockCapabilitiesApi } from '@/services/blockCapabilitiesApi'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { flowsApi } from '@/services/flowsApi'
  import { logsApi } from '@/services/logsApi'
  import { taskRunsApi } from '@/services/taskRunsApi'
  import { workQueuesApi } from '@/services/workQueuesApi'
  import { healthCheck } from '@/utilities/api'
  import { can } from '@/utilities/permissions'

  provide(blockCapabilitiesApiKey, blockCapabilitiesApi)
  provide(blockDocumentsApiKey, blockDocumentsApi)
  provide(blockSchemasApiKey, blockSchemasApi)
  provide(blockTypesApiKey, blockTypesApi)
  provide(deploymentsApiKey, deploymentsApi)
  provide(flowRunsApiKey, flowRunsApi)
  provide(flowsApiKey, flowsApi)
  provide(logsApiKey, logsApi)
  provide(taskRunsApiKey, taskRunsApi)
  provide(workQueuesApiKey, workQueuesApi)

  provide(canKey, can)

  provide(blockCatalogViewRouteKey, routes.blocksCatalogView)
  provide(blockCatalogCreateRouteKey, routes.blocksCatalogCreate)
  provide(blockCatalogRouteKey, routes.blocksCatalog)
  provide(blockEditRouteKey, routes.blockEdit)
  provide(blockRouteKey, routes.block)
  provide(blocksRouteKey, routes.blocks)
  provide(deploymentRouteKey, routes.deployment)
  provide(editDeploymentRouteKey, routes.deploymentEdit)
  provide(deploymentsRouteKey, routes.deployments)
  provide(editQueueRouteKey, routes.workQueueEdit)
  provide(flowRouteKey, routes.flow)
  provide(flowRunCreateRouteKey, routes.flowRunCreate)
  provide(flowRunRouteKey, routes.flowRun)
  provide(flowRunsRouteKey, routes.flowRuns)
  provide(flowsRouteKey, routes.flows)
  provide(settingsRouteKey, routes.settings)
  provide(workQueueCreateRouteKey, routes.workQueueCreate)
  provide(workQueueRouteKey, routes.workQueue)
  provide(workQueueCreateRouteKey, routes.workQueueCreate)
  provide(editQueueRouteKey, routes.workQueueEdit)
  provide(notificationsApiKey, notificationsApi)
  provide(notificationCreateRouteKey, routes.notificationCreate)
  provide(editNotificationRouteKey, routes.notificationEdit)
  provide(notificationsRouteKey, routes.notifications)
  provide(taskRunRouteKey, routes.taskRun)
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
  text-slate-900;
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
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
  }
}
</style>
