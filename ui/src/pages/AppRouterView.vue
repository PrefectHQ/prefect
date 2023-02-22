<template>
  <div class="app-router-view">
    <template v-if="!media.lg">
      <PGlobalSidebar class="app-router-view__mobile-menu">
        <template #upper-links>
          <p-icon icon="PrefectGradient" class="app-router-view__prefect-icon" />
        </template>
        <template #bottom-links>
          <PIcon icon="MenuIcon" class="app-router-view__menu-icon" @click="toggle" />
        </template>
      </PGlobalSidebar>
    </template>
    <ContextSidebar v-if="showMenu" class="app-router-view__sidebar" @click="close" />
    <router-view class="app-router-view__view">
      <template #default="{ Component }">
        <transition name="app-router-view-fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </template>
    </router-view>
  </div>
</template>

<script lang="ts" setup>
  import { PGlobalSidebar, PIcon, media, showToast } from '@prefecthq/prefect-design'
  import { workspaceApiKey, canKey as designCanKey, createWorkspaceRoutes, workspaceRoutesKey } from '@prefecthq/prefect-ui-library'
  import { computed, provide, watchEffect } from 'vue'
  import { RouterView } from 'vue-router'
  import ContextSidebar from '@/components/ContextSidebar.vue'
  import { useApiConfig } from '@/compositions/useApiConfig'
  import { useCreateCan } from '@/compositions/useCreateCan'
  import { useMobileMenuOpen } from '@/compositions/useMobileMenuOpen'
  import { createPrefectApi, prefectApiKey } from '@/utilities/api'
  import { canKey } from '@/utilities/permissions'

  const { can } = useCreateCan()
  const { config } = await useApiConfig()
  const api = createPrefectApi(config)
  const routes = createWorkspaceRoutes()

  provide(canKey, can)
  provide(designCanKey, can)
  provide(prefectApiKey, api)
  provide(workspaceApiKey, api)
  provide(workspaceRoutesKey, routes)

  api.health.isHealthy().then(healthy => {
    if (!healthy) {
      showToast(`Can't connect to Server API at ${config.baseUrl}. Check that it's accessible from your machine.`, 'error', { timeout: false })
    }
  })

  const { mobileMenuOpen, toggle, close } = useMobileMenuOpen()
  const showMenu = computed(() => media.lg || mobileMenuOpen.value)

  watchEffect(() => document.body.classList.toggle('body-scrolling-disabled', showMenu.value && !media.lg))
</script>

<style>
.body-scrolling-disabled { @apply
  overflow-hidden
}

.app-router-view { @apply
  text-foreground
  bg-background
  dark:bg-background-400
  flex
  flex-col
}

.app-router-view {
  --prefect-scroll-margin: theme('spacing.20');
  min-height: 100vh;
}

.app-router-view__prefect-icon { @apply
  w-6
  h-6
}

.app-router-view__menu-icon { @apply
  text-white
  w-6
  h-6
  cursor-pointer
}

.app-router-view__view { @apply
  relative
  z-0;

  /* The 1px flex-basis is important because it allows us to use height: 100% without additional flexing */
  flex: 1 0 1px;
  height: 100%;
}

@screen lg {
  .app-router-view {
    --prefect-scroll-margin: theme('spacing.2');
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
  }
}

.app-router-view-fade-enter-active,
.app-router-view-fade-leave-active {
  transition: opacity 0.25s ease;
}

.app-router-view-fade-enter-from,
.app-router-view-fade-leave-to {
  opacity: 0;
}
</style>