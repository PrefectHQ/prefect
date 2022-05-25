<template>
  <p-layout-default class="settings">
    <template #header>
      Settings
    </template>

    <SettingsCodeBlock class="settings--code-block" :engine-settings="engineSettings" />

    <div>Version</div>
    <div>
      {{ version }}
    </div>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import SettingsCodeBlock from '@/components/SettingsCodeBlock.vue'
  import { adminApi } from '@/services/adminApi'

  const engineSettings = await adminApi.getSettings()
  const version = await adminApi.getVersion()
</script>