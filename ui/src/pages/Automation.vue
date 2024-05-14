<template>
  <p-layout-default v-if="automation" class="automation">
    <template #header>
      <PageHeading :crumbs="crumbs">
        <template #actions>
          <AutomationToggle :automation="automation" @update="subscription.refresh" />
          <AutomationMenu :automation="automation" @delete="goToAutomations" />
        </template>
      </PageHeading>
    </template>
    <p-content>
      <p-key-value label="Description" :value="automation.description" />

      <p-content secondary>
        <span class="automation-card__label">Trigger</span>
        <AutomationTriggerDescription :trigger="automation.trigger" />
      </p-content>

      <p-content secondary>
        <span class="automation-card__label">{{ toPluralString('Action', automation.actions.length) }}</span>
        <template v-for="action in automation.actions" :key="action.id">
          <p-card><AutomationActionDescription :action="action" /></p-card>
        </template>
      </p-content>
    </p-content>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { Crumb } from '@prefecthq/prefect-design'
  import { PageHeading, AutomationMenu, AutomationToggle, AutomationTriggerDescription, AutomationActionDescription, toPluralString, useWorkspaceRoutes } from '@prefecthq/prefect-ui-library'
  import { useRouteParam, useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { usePrefectApi } from '@/compositions/usePrefectApi'

  const routes = useWorkspaceRoutes()
  const router = useRouter()
  const api = usePrefectApi()
  const automationId = useRouteParam('automationId')

  const subscription = useSubscription(api.automations.getAutomation, [automationId])
  const automation = computed(() => subscription.response)

  const name = computed(() => automation.value?.name ?? '')

  const crumbs = computed<Crumb[]>(() => [
    { text: 'Automations', to: routes.automations() },
    { text: name.value },
  ])

  const title = computed<string>(() => {
    if (automation.value) {
      return `Automation: ${automation.value.name}`
    }

    return 'Automation'
  })

  usePageTitle(title)

  function goToAutomations(): void {
    router.push(routes.automations())
  }
</script>