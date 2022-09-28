<template>
  <p-layout-default v-if="blockDocument" class="block-view">
    <template #header>
      <PageHeadingBlock :block-document="blockDocument" @delete="routeToBlocks" />
    </template>

    <BlockDocumentCard :block-document="blockDocument" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingBlock, BlockDocumentCard } from '@prefecthq/orion-design'
  import { useSubscriptionWithDependencies, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'
  import { blockDocumentsApi } from '@/services/blockDocumentsApi'

  const router = useRouter()
  const blockDocumentId = useRouteParam('blockDocumentId')
  const blockDocumentSubscriptionsArgs = computed<Parameters<typeof blockDocumentsApi.getBlockDocument> | null >(() => {
    if (!blockDocumentId.value) {
      return null
    }

    return [blockDocumentId.value]
  })
  const blockDocumentSubscription = useSubscriptionWithDependencies(blockDocumentsApi.getBlockDocument, blockDocumentSubscriptionsArgs)
  const blockDocument = computed(() => blockDocumentSubscription.response)

  const routeToBlocks = (): void => {
    router.push(routes.blocks())
  }

  const title = computed(() => {
    if (!blockDocument.value) {
      return 'Block'
    }
    return `Block: ${blockDocument.value.name}`
  })
  usePageTitle(title)
</script>