<template>
  <p-layout-default class="settings">
    <template #header>
      <PageHeading :crumbs="crumbs">
        <template #actions>
          <p-key-value label="Version" :value="version" alternate />
        </template>
      </PageHeading>
    </template>

    <p-label label="Color Mode" class="settings__color-mode">
      <ColorModeSelect v-model:selected="activeColorMode" />
    </p-label>

    <p-label label="Orion Settings">
      <SettingsCodeBlock class="settings__code-block" :engine-settings="engineSettings" />
    </p-label>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeading, ColorModeSelect } from '@prefecthq/orion-design'
  import SettingsCodeBlock from '@/components/SettingsCodeBlock.vue'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { adminApi } from '@/services/adminApi'
  import { activeColorMode } from '@/utilities/colorMode'

  const crumbs = [{ text: 'Settings' }]

  const engineSettings = await adminApi.getSettings()
  const version = await adminApi.getVersion()

  usePageTitle('Settings')
</script>

<style>
.settings__color-mode { @apply
  w-96
  max-w-full
}

.settings__code-block { @apply
  max-w-full
  overflow-x-auto
}
</style>