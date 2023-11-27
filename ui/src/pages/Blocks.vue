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
        <BlockDocumentsTable @delete="subscription.refresh" />
      </template>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingBlocks, BlockDocumentsTable, BlocksPageEmptyState, useWorkspaceApi } from '@prefecthq/prefect-ui-library'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const api = useWorkspaceApi()
  const subscription = useSubscription(api.blockDocuments.getBlockDocumentsCount)
  const empty = computed(() => subscription.executed && subscription.response == 0)
  const loaded = computed(() => subscription.executed)

  usePageTitle('Blocks')
</script>