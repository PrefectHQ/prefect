<template>
  <div class="app-router-view">
    <template v-if="!media.lg && !$route.meta.public">
      <PGlobalSidebar class="app-router-view__mobile-menu">
        <template #upper-links>
          <router-link :to="appRoutes.root()">
            <p-icon icon="Prefect" class="app-router-view__prefect-icon" />
          </router-link>
        </template>
        <template #bottom-links>
          <p-button small icon="Bars3Icon" class="app-router-view__menu-icon" @click="toggle" />
        </template>
      </PGlobalSidebar>
    </template>
    <ContextSidebar v-if="showMenu && !$route.meta.public" class="app-router-view__sidebar" @click="close" />
    <router-view :class="['app-router-view__view', { 'app-router-view__view--public': $route.meta.public }]">
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
  import router, { routes as appRoutes } from '@/router'
  import { createPrefectApi, prefectApiKey } from '@/utilities/api'
  import { canKey } from '@/utilities/permissions'
  import { UiSettings } from '@/services/uiSettings'

  const { can } = useCreateCan()
  const { config } = await useApiConfig()
  const api = createPrefectApi(config)
  const routes = createWorkspaceRoutes()

  provide(canKey, can)
  provide(designCanKey, can)
  provide(prefectApiKey, api)
  provide(workspaceApiKey, api)
  provide(workspaceRoutesKey, routes)


  api.admin.authCheck().then(status_code => {
    if (status_code == 401) {
      if (router.currentRoute.value.name !== 'login') {
        showToast('Authentication failed.', 'error', { timeout: false })
        router.push({
          name: 'login', 
          query: { redirect: router.currentRoute.value.fullPath }
        })
      }
    } else {
      api.health.isHealthy().then(healthy => {
        if (!healthy) {
          showToast(`Can't connect to Server API at ${config.baseUrl}. Check that it's accessible from your machine.`, 'error', { timeout: false })
        }
      })
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
  flex
  flex-col
  bg-no-repeat
  overflow-auto;
  --prefect-scroll-margin: theme('spacing.20');
  height: 100vh;
  background-image: url('/decorative_iso-pixel-grid_light.svg');
  background-attachment: fixed;
  background-position: bottom -140px left -140px;
}

.dark .app-router-view {
  background-image: url('/decorative_iso-pixel-grid_dark.svg');
}

.app-router-view__prefect-icon { @apply
  w-7
  h-7
}

.app-router-view__mobile-menu { @apply
  h-auto
  py-3
}

.app-router-view__sidebar { @apply
  bg-floating
  top-[54px]
  lg:bg-transparent
  lg:top-0
}

.app-router-view__sidebar .p-context-sidebar__header { @apply
  hidden
  lg:block
}

.app-router-view__view {
  /* The 1px flex-basis is important because it allows us to use height: 100% without additional flexing */
  flex: 1 0 1px;
  height: 100%;
}

.app-router-view__view--public { @apply
  flex
  items-center
  justify-center;
  grid-column: 1 / -1;
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