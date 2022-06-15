<template>
  <p-layout-default v-if="blockDocument" class="block-edit">
    <PageHeadingBlockEdit :block-document="blockDocument" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingBlockEdit, useRouteParam } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { blockDocumentsApi } from '@/services/blockDocumentsApi'

  const blockDocumentId = useRouteParam('blockDocumentId')
  const blockDocumentSubscription = useSubscription(blockDocumentsApi.getBlockDocument, [blockDocumentId])
  const blockDocument = computed(() => blockDocumentSubscription.response)
</script>