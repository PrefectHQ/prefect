<template>
  <router-view class="router-view">
    <template #default="{ Component }">
      <transition name="router-view-fade" mode="out-in">
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
.router-view { @apply
  relative
  z-0
}

.router-view-fade-enter-active,
.router-view-fade-leave-active {
  transition: opacity 0.25s ease;
}

.router-view-fade-enter-from,
.router-view-fade-leave-to {
  opacity: 0;
}
</style>