<template>
  <p-layout-default class="automations">
    <template #header>
      <PageHeading :crumbs="crumbs">
        <template #after-crumbs>
          <p-button size="sm" icon="PlusIcon" :to="routes.automationCreate()" />
        </template>

        <template v-if="!empty" #actions>
          <DocumentationButton :to="localization.docs.automations">
            Documentation
          </DocumentationButton>
        </template>
      </PageHeading>
    </template>
    <template v-if="loaded">
      <template v-if="empty">
        <AutomationsPageEmptyState />
      </template>
      <template v-else>
        <ResultsCount :count="automations.length" label="automation" />

        <p-virtual-scroller :items="automations" class="automations-list">
          <template #default="{ item: automation }">
            <AutomationCard :automation="automation" @update="subscription.refresh" />
          </template>
        </p-virtual-scroller>
      </template>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeading, ResultsCount, AutomationsPageEmptyState, DocumentationButton, localization, useWorkspaceRoutes } from '@prefecthq/prefect-ui-library'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import AutomationCard from '@/components/AutomationCard.vue'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { usePrefectApi } from '@/compositions/usePrefectApi'

  const routes = useWorkspaceRoutes()

  usePageTitle('Automations')

  const crumbs = [{ text: 'Automations' }]
  const api = usePrefectApi()

  const subscription = useSubscription(api.automations.getAutomations)
  const automations = computed(() => subscription.response ?? [])

  const loaded = computed(() => subscription.executed)
  const empty = computed(() => automations.value.length === 0)
</script>

<style>
.automations {
  --virtual-scroller-item-gap: theme('spacing.2')
}
</style>