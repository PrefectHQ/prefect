<template>
  <p-layout-default class="blocks">
    <template #header>
      <PageHeadingBlocks />
    </template>
    <template v-if="loaded">
      <template v-if="empty">
        <BlocksPageEmptyState />
      </template>
      <template v-else>
        <BlockDocumentsTable :block-documents="blockDocuments" @delete="blockDocumentsSubscription.refresh" />
      </template>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingBlocks, BlockDocumentsTable, BlocksPageEmptyState } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { blockDocumentsApi } from '@/services/blockDocumentsApi'

  const blockDocumentsSubscription = useSubscription(blockDocumentsApi.getBlockDocuments)
  const blockDocuments = computed(() => blockDocumentsSubscription.response ?? [])
  const empty = computed(() => blockDocumentsSubscription.executed && blockDocuments.value.length == 0)
  const loaded = computed(() => blockDocumentsSubscription.executed)

  usePageTitle('Blocks')
</script>