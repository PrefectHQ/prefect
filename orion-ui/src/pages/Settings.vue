<template>
  <div class="settings">
    Settings
  </div>

  <SettingsCodeBlock :engine-settings="engineSettings" />

  <div>Version</div>
  <div>
    {{ version }}
  </div>
</template>

<script lang="ts" setup>
  import SettingsCodeBlock from '@/components/SettingsCodeBlock.vue'
  import { adminApi } from '@/services/adminApi'

  const engineSettings = await adminApi.getSettings()
  const version = await adminApi.getVersion()
</script>

<style>
.settings {}
</style>
