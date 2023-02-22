<template>
  <div class="app" data-teleport-target="app">
    <suspense>
      <AppRouterView />
    </suspense>
  </div>
</template>

<script lang="ts" setup>
  import { useColorTheme } from '@prefecthq/prefect-design'
  import AppRouterView from '@/pages/AppRouterView.vue'

  useColorTheme()
</script>
