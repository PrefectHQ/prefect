<template>
  <p-layout-default v-if="blockType" class="blocks-catalog-create">
    <template #header>
      <PageHeadingBlocksCatalogCreate :block-type="blockType" />
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingBlocksCatalogCreate, useRouteParam, titleCase } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { blockTypesApi } from '@/services/blockTypesApi'

  const blockTypeNameParam = useRouteParam('blockTypeName')
  const blockTypeName = computed(() => titleCase(blockTypeNameParam.value))
  const blockTypeSubscription = useSubscription(blockTypesApi.getBlockTypeByName, [blockTypeName])
  const blockType = computed(() => blockTypeSubscription.response)
</script>