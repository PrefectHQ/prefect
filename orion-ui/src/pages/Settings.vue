<template>
  <p-layout-default class="settings">
    <template #header>
      <PageHeading :crumbs="crumbs">
        <template #actions>
          <p-key-value label="Version" :value="version" />
        </template>
      </PageHeading>
    </template>

    <SettingsCodeBlock class="settings--code-block" :engine-settings="engineSettings" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeading } from '@prefecthq/orion-design'
  import SettingsCodeBlock from '@/components/SettingsCodeBlock.vue'
  import { adminApi } from '@/services/adminApi'

  const crumbs = [{ text: 'Settings' }]

  const engineSettings = await adminApi.getSettings()
  const version = await adminApi.getVersion()
</script>