<template>
  <div class="app" data-teleport-target="app">
    <suspense>
      <router-view />
    </suspense>
  </div>
</template>

<script lang="ts" setup>
  import { useColorTheme } from '@prefecthq/prefect-design'

  useColorTheme()
</script>
