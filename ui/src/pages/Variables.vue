<template>
  <p-layout-default class="variables">
    <template #header>
      <PageHeadingVariables @create="refresh" />
    </template>

    <VariablesTable ref="table" @delete="refresh" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { localization, PageHeadingVariables, VariablesTable } from '@prefecthq/prefect-ui-library'
  import { ref } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const table = ref<typeof VariablesTable>()

  const refresh = (): void => {
    table.value?.refreshSubscriptions()
  }

  usePageTitle(localization.info.variables)
</script>