<template>
  <p-layout-default class="settings">
    <template #header>
      <PageHeading :crumbs="crumbs">
        <template #actions>
          <p-key-value class="settings__version" label="Version" :value="version" alternate />
        </template>
      </PageHeading>
    </template>

    <p-label label="Theme">
      <p-theme-toggle />
    </p-label>

    <p-label label="Color Mode" class="settings__color-mode">
      <ColorModeSelect v-model:selected="activeColorMode" />
    </p-label>

    <p-label label="Server Settings">
      <SettingsCodeBlock class="settings__code-block" :engine-settings="engineSettings" />
    </p-label>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeading, ColorModeSelect } from '@prefecthq/prefect-ui-library'
  import SettingsCodeBlock from '@/components/SettingsCodeBlock.vue'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { usePrefectApi } from '@/compositions/usePrefectApi'
  import { activeColorMode } from '@/utilities/colorMode'

  const crumbs = [{ text: 'Settings' }]

  const api = usePrefectApi()
  const [engineSettings, version] = await Promise.all([
    api.admin.getSettings(),
    api.admin.getVersion(),
  ])

  usePageTitle('Settings')
</script>

<style>
.settings__version { @apply
  w-auto
}

.settings__color-mode { @apply
  w-96
  max-w-full
}

.settings__code-block { @apply
  max-w-full
  overflow-x-auto
}
</style>