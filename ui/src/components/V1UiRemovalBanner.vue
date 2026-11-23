<template>
  <div v-if="!dismissed" class="v1-ui-removal-banner" role="alert">
    <div class="v1-ui-removal-banner__copy">
      <p class="v1-ui-removal-banner__title">
        The V1 UI will be removed in Prefect 3.10
      </p>
      <p class="v1-ui-removal-banner__description">
        Switch to the V2 UI now so you're ready when you upgrade.
      </p>
    </div>
    <div class="v1-ui-removal-banner__actions">
      <p-button small @click="dismiss">
        Dismiss
      </p-button>
      <p-button v-if="canSwitchToV2" small primary @click="switchToV2">
        Switch to V2 UI
      </p-button>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { useStorage } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { useRoute } from 'vue-router'
  import { Settings, UiSettings } from '@/services/uiSettings'
  import { isUiAvailable, switchToV2Ui } from '@/utilities/uiVersion'

  const route = useRoute()
  const browserUiSettings = ref<Settings | null>(UiSettings.settings)
  const canSwitchToV2 = computed(() => {
    return browserUiSettings.value !== null && isUiAvailable(browserUiSettings.value, 'v2')
  })
  const { value: dismissed } = useStorage('session', 'prefect-v1-ui-removal-banner-dismissed', false)

  void UiSettings.loadOptional(route.path).then(settings => {
    browserUiSettings.value = settings
  })

  function dismiss(): void {
    dismissed.value = true
  }

  function switchToV2(): void {
    if (browserUiSettings.value === null) {
      return
    }

    switchToV2Ui(browserUiSettings.value, route.path)
  }
</script>

<style>
.v1-ui-removal-banner { @apply
  flex
  flex-col
  gap-3
  border-b
  border-amber-300
  bg-amber-50
  px-5
  py-3
  lg:flex-row
  lg:items-center
  lg:justify-between
}

.v1-ui-removal-banner__copy { @apply
  flex
  flex-col
  gap-0.5
}

.v1-ui-removal-banner__title { @apply
  text-sm
  font-semibold
  text-amber-950
}

.v1-ui-removal-banner__description { @apply
  text-sm
  text-amber-900
}

.dark .v1-ui-removal-banner { @apply
  border-amber-800
  bg-amber-950
}

.dark .v1-ui-removal-banner__title { @apply
  text-amber-50
}

.dark .v1-ui-removal-banner__description { @apply
  text-amber-200
}

.v1-ui-removal-banner__actions { @apply
  flex
  flex-wrap
  gap-2
  justify-end
}
</style>
