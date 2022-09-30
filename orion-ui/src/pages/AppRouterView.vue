<template>
  <router-view class="app-router-view">
    <template #default="{ Component }">
      <transition name="app-router-view-fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </template>
  </router-view>
</template>

<script lang="ts" setup>
  import { createApi, workspaceApiKey } from '@prefecthq/orion-design'
  import { provide } from 'vue'
  import { UiSettings } from '@/services/uiSettings'


  const baseUrl = await UiSettings.get('apiUrl')
  const api = createApi({
    baseUrl,
  })

  provide(workspaceApiKey, api)
</script>

<style>
.app-router-view { @apply
  relative
  z-0
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