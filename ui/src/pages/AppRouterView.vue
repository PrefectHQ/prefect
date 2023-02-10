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
  import { PGlobalSidebar, PIcon, media } from '@prefecthq/prefect-design'
  import { createApi, workspaceApiKey, createCan, canKey as designCanKey, workspacePermissions, createWorkspaceRoutes, workspaceRoutesKey } from '@prefecthq/prefect-ui-library'
  import { computed, provide, ref, watchEffect } from 'vue'
  import { RouterView } from 'vue-router'
  import ContextSidebar from '@/components/ContextSidebar.vue'
  import { UiSettings } from '@/services/uiSettings'
  import { canKey } from '@/utilities/permissions'

  const baseUrl = await UiSettings.get('apiUrl')
  const api = createApi({
    baseUrl,
  })
  const flags = await UiSettings.get('flags')

  const can = createCan([
    ...workspacePermissions,
    ...flags,
  ])

  const routes = createWorkspaceRoutes()

  provide(canKey, can)
  provide(designCanKey, can)
  provide(workspaceApiKey, api)
  provide(workspaceRoutesKey, routes)

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