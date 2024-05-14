<template>
  <p-layout-default class="workspace-automation-create">
    <template #header>
      <PageHeading :crumbs="crumbs">
        <template #actions>
          <DocumentationButton :to="localization.docs.automations">
            Documentation
          </DocumentationButton>
        </template>
      </PageHeading>
    </template>

    <AutomationWizard :automation="automation" editing @submit="submit" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { BreadCrumbs, showToast } from '@prefecthq/prefect-design'
  import { PageHeading, DocumentationButton, getApiErrorMessage, useWorkspaceRoutes, localization } from '@prefecthq/prefect-ui-library'
  import { useRouteParam } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import AutomationWizard from '@/components/AutomationWizard.vue'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { usePrefectApi } from '@/compositions/usePrefectApi'
  import { Automation } from '@/types/automation'

  const api = usePrefectApi()
  const routes = useWorkspaceRoutes()
  const router = useRouter()
  const automationId = useRouteParam('automationId')
  const automation = await api.automations.getAutomation(automationId.value)

  usePageTitle(`Edit Automation: ${automation.name}`)

  const crumbs = computed<BreadCrumbs>(() => [
    { text: 'Automations', to: routes.automations() },
    { text: automation.name },
  ])

  async function submit(automation: Automation): Promise<void> {
    try {
      await api.automations.updateAutomation(automationId.value, automation)

      showToast(localization.success.automationUpdate)

      router.push(routes.automations())
    } catch (error) {
      console.error(error)
      const message = getApiErrorMessage(error, localization.error.automationUpdate)
      showToast(message, 'error', { timeout: false })
    }
  }
</script>