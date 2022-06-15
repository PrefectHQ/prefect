<template>
  <p-layout-default v-if="blockType" class="blocks-catalog-create">
    <PageHeadingBlocksCatalogCreate :block-type="blockType" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingBlocksCatalogCreate, useRouteParam } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { blockTypesApi } from '@/services/blockTypesApi'

  const blockTypeName = useRouteParam('blockTypeName')
  const blockTypeSubscription = useSubscription(blockTypesApi.getBlockTypeByName, [blockTypeName])
  const blockType = computed(() => blockTypeSubscription.response)
</script>