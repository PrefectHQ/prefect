<template>
  <div>
    <PageHeader icon="flow">
      Flows
    </PageHeader>

    <FlowsPageFlowList :filter="filter" />
  </div>
</template>

<script lang="ts" setup>
  import { FlowsPageFlowList, PageHeader, UnionFilters, workspaceDashboardKey } from '@prefecthq/orion-design'
  import { computed, provide, ref } from 'vue'

  // todo: create a routes object with methods like nebula has
  provide(workspaceDashboardKey, {
    name: 'Dashboard',
  })

  const sort = ref<'STATE_ASC' | 'STATE_DESC'>('STATE_ASC')

  const filter = computed<UnionFilters>(() => ({
    sort: sort.value,
  }))
</script>
