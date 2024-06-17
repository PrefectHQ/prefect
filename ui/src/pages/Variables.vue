<template>
  <p-layout-default class="variables">
    <template #header>
      <PageHeadingVariablesV2 @create="refresh" />
    </template>
    <template v-if="loaded">
      <template v-if="empty">
        <VariablesV2PageEmptyState @create="refresh" />
      </template>
      <template v-else>
        <VariablesV2Table ref="table" @delete="refresh" @update="refresh" />
      </template>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { localization, PageHeadingVariablesV2, VariablesV2Table, VariablesV2PageEmptyState, useWorkspaceApi } from '@prefecthq/prefect-ui-library'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { ref, computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const table = ref<typeof VariablesV2Table>()
  const refresh = (): void => {
    variablesSubscription.value.refresh()
    table.value?.refreshSubscriptions()
  }
  const api = useWorkspaceApi()

  const variablesSubscription = computed(() => useSubscription(api.variables.getVariablesV2))
  const empty = computed(() => variablesSubscription.value.executed && variablesSubscription.value.response?.length === 0)
  const loaded = computed(() => variablesSubscription.value.executed)
  usePageTitle(localization.info.variables)
</script>