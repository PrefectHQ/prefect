<template>
  <p-layout-default class="blocks-catalog">
    <template #header>
      <PageHeadingBlocksCatalog />
    </template>

    <BlockTypeList v-model:capability="capability" :block-types="blockTypes" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingBlocksCatalog, BlockTypeList, useWorkspaceApi, useBlockTypesFilter } from '@prefecthq/prefect-ui-library'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const api = useWorkspaceApi()
  const capability = ref<string | null>(null)
  const blockCapabilities = computed(() => capability.value ? [capability.value] : [])

  const { filter } = useBlockTypesFilter({
    blockSchemas: {
      blockCapabilities,
    },
  })
  const blockTypesSubscription = useSubscription(api.blockTypes.getBlockTypes, [filter])
  const blockTypes = computed(() => blockTypesSubscription.response ?? [])

  usePageTitle('Blocks Catalog')
</script>