<template>
  <div class="settings">
    Settings
  </div>

  <div>
    {{ engineSettings }}
  </div>

  <div>
    Version
  </div>
  <div>
    {{ version }}
  </div>
</template>

<script lang="ts" setup>
  import { adminApi } from '@/services/adminApi'

  const engineSettings = await adminApi.getSettings()
  const  version  = await adminApi.getVersion()
</script>

<style>
.settings {}
</style>