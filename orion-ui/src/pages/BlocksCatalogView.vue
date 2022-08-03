<template>
  <p-layout-default v-if="blockType" class="blocks-catalog-view">
    <template #header>
      <PageHeadingBlocksCatalogView :block-type="blockType" />
    </template>

    <BlockTypeCard :block-type="blockType" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingBlocksCatalogView, BlockTypeCard } from '@prefecthq/orion-design'
  import { useRouteParam, useSubscriptionWithDependencies } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { blockTypesApi } from '@/services/blockTypesApi'

  const blockTypeSlugParam = useRouteParam('blockTypeSlug')
  const blockTypeSubscriptionArgs = computed<Parameters<typeof blockTypesApi.getBlockTypeBySlug> | null>(() => {
    if (!blockTypeSlugParam.value) {
      return null
    }

    return [blockTypeSlugParam.value]
  })

  const blockTypeSubscription = useSubscriptionWithDependencies(blockTypesApi.getBlockTypeBySlug, blockTypeSubscriptionArgs)
  const blockType = computed(() => blockTypeSubscription.response)
</script>