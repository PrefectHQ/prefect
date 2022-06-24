<template>
  <p-layout-default v-if="blockDocument" class="block">
    <template #header>
      <PageHeadingBlock :block-document="blockDocument" />
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingBlock } from '@prefecthq/orion-design'
  import { useSubscription, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { blockDocumentsApi } from '@/services/blockDocumentsApi'

  const blockDocumentId = useRouteParam('blockDocumentId')
  const blockDocumentSubscription = useSubscription(blockDocumentsApi.getBlockDocument, [blockDocumentId])
  const blockDocument = computed(() => blockDocumentSubscription.response)
</script>