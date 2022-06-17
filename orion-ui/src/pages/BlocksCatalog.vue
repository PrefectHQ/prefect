<template>
  <p-layout-default class="blocks-catalog">
    <template #header>
      <PageHeadingBlocksCatalog />
    </template>

    <template v-if="loaded">
      <BlockTypeList :block-types="blockTypes" />
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingBlocksCatalog, BlockTypeList } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { blockTypesApi } from '@/services/blockTypesApi'

  const blockTypesSubscription = useSubscription(blockTypesApi.getBlockTypes)
  const blockTypes = computed(() => blockTypesSubscription.response ?? [])
  const loaded = computed(() => blockTypesSubscription.executed)
</script>