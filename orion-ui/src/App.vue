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
    canKey,
    createWorkspaceRoutes,
    workspaceRoutesKey
  } from '@prefecthq/orion-design'
  import { PGlobalSidebar, PIcon, media } from '@prefecthq/prefect-design'
  import { computed, provide, ref, watchEffect } from 'vue'
  import ContextSidebar from '@/components/ContextSidebar.vue'
  import AppRouterView from '@/pages/AppRouterView.vue'
  import { healthCheck } from '@/utilities/api'
  import { can } from '@/utilities/permissions'

  const routes = createWorkspaceRoutes()

  provide(workspaceRoutesKey, routes)
  provide(canKey, can)

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
