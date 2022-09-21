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
      <ColorModeSelect v-model:selected="mode" />
    </p-label>

    <p-label label="Orion Settings">
      <SettingsCodeBlock class="settings__code-block" :engine-settings="engineSettings" />
    </p-label>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeading, ColorModeSelect, ColorMode } from '@prefecthq/orion-design'
  import { ref, watchEffect } from 'vue'
  import SettingsCodeBlock from '@/components/SettingsCodeBlock.vue'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { adminApi } from '@/services/adminApi'
  import { getActiveColorMode, setActiveColorMode } from '@/utilities/colorMode'

  const crumbs = [{ text: 'Settings' }]

  const engineSettings = await adminApi.getSettings()
  const version = await adminApi.getVersion()
  const mode = ref<ColorMode>(getActiveColorMode())

  usePageTitle('Settings')

  watchEffect(() => setActiveColorMode(mode.value))
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