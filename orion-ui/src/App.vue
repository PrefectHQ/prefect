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
      <router-view class="app__router-view">
        <template #default="{ Component }">
          <transition name="app__router-view-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </template>
      </router-view>
    </suspense>
  </div>
</template>

<script lang="ts" setup>
  import {
    deploymentsApiKey,
    flowRunsApiKey,
    flowsApiKey,
    logsApiKey,
    taskRunsApiKey,
    workQueuesApiKey,
    canKey,
    flowRunsRouteKey,
    flowsRouteKey,
    deploymentsRouteKey,
    workQueuesRouteKey,
    settingsRouteKey,
    flowRunRouteKey,
    flowRouteKey,
    deploymentRouteKey,
    workQueueRouteKey,
    workQueueCreateRouteKey,
    editQueueRouteKey
  } from '@prefecthq/orion-design'
  import { PGlobalSidebar, PIcon, media } from '@prefecthq/prefect-design'
  import { computed, provide, ref, watchEffect } from 'vue'
  import { routes } from '@/router/routes'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { flowsApi } from '@/services/flowsApi'
  import { logsApi } from '@/services/logsApi'
  import { taskRunsApi } from '@/services/taskRunsApi'
  import { workQueuesApi } from '@/services/workQueuesApi'
  import { can } from '@/utilities/permissions'

  provide(deploymentsApiKey, deploymentsApi)
  provide(flowRunsApiKey, flowRunsApi)
  provide(flowsApiKey, flowsApi)
  provide(logsApiKey, logsApi)
  provide(taskRunsApiKey, taskRunsApi)
  provide(workQueuesApiKey, workQueuesApi)
  provide(canKey, can)
  provide(flowRunsRouteKey, routes.flowRuns)
  provide(flowsRouteKey, routes.flows)
  provide(deploymentsRouteKey, routes.deployments)
  provide(workQueuesRouteKey, routes.workQueues)
  provide(settingsRouteKey, routes.settings)
  provide(flowRunRouteKey, routes.flowRun)
  provide(flowRouteKey, routes.flow)
  provide(deploymentRouteKey, routes.deployment)
  provide(workQueueRouteKey, routes.workQueue)
  provide(workQueueCreateRouteKey, routes.workQueueCreate)
  provide(editQueueRouteKey, routes.workQueueEdit)

  const mobileMenuOpen = ref(false)
  const showMenu = computed(() => media.lg || mobileMenuOpen.value)

  function toggle(): void {
    mobileMenuOpen.value = !mobileMenuOpen.value
  }

  function close(): void {
    mobileMenuOpen.value = false
  }

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

.app__router-view { @apply
  relative
  z-0
}

.app__router-view-fade-enter-active,
.app__router-view-fade-leave-active {
  transition: opacity 0.25s ease;
}

.app__router-view-fade-enter-from,
.app__router-view-fade-leave-to {
  opacity: 0;
}

@screen lg {
  .app {
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
  }
}
</style>
