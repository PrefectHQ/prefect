<template>
  <p-layout-default class="blocks-catalog">
    <template #header>
      <PageHeadingBlocksCatalog />
    </template>

    <BlockTypeList v-model:capability="capability" :block-types="blockTypes" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingBlocksCatalog, BlockTypeList, BlockTypeFilter, useWorkspaceApi } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const api = useWorkspaceApi()
  const capability = ref<string | null>(null)
  const filter = computed<BlockTypeFilter>(() => {
    if (!capability.value) {
      return {}
    }

    return {
      blockSchemas: {
        blockCapabilities: {
          all_: [capability.value],
        },
      },
    }
  })
  const blockTypesSubscription = useSubscription(api.blockTypes.getBlockTypes, [filter])
  const blockTypes = computed(() => blockTypesSubscription.response ?? [])

  usePageTitle('Blocks Catalog')
</script>