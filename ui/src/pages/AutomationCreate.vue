<template>
  <p-layout-default class="automation-create">
    <template #header>
      <PageHeading :crumbs>
        <template #actions>
          <DocumentationButton :to="localization.docs.automations">
            Documentation
          </DocumentationButton>
        </template>
      </PageHeading>
    </template>

    <AutomationWizard :automation @submit="submit" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { BreadCrumbs, showToast } from '@prefecthq/prefect-design'
  import { PageHeading, DocumentationButton, getApiErrorMessage, localization, useCreateAutomationQueryParams, useWorkspaceRoutes } from '@prefecthq/prefect-ui-library'
  import { useRouter } from 'vue-router'
  import AutomationWizard from '@/components/AutomationWizard.vue'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { usePrefectApi } from '@/compositions/usePrefectApi'
  import { Automation } from '@/types/automation'

  usePageTitle('Create Automation')

  const api = usePrefectApi()
  const routes = useWorkspaceRoutes()
  const router = useRouter()

  const crumbs: BreadCrumbs = [
    { text: 'Automations', to: routes.automations() },
    { text: 'Create' },
  ]

  const { getActions, getTrigger } = useCreateAutomationQueryParams()

  const automation = await getAutomationTemplate()

  async function getAutomationTemplate(): Promise<Partial<Automation>> {
    const automation: Partial<Automation> = {}

    const [trigger, actions] = await Promise.all([
      getTrigger(),
      getActions(),
    ])

    if (trigger) {
      automation.trigger = trigger
    }

    if (actions) {
      automation.actions = actions
    }

    return automation
  }

  async function submit(automation: Automation): Promise<void> {
    try {
      await api.automations.createAutomation(automation)

      showToast(localization.success.automationCreate)

      router.push(routes.automations())
    } catch (error) {
      console.error(error)
      const message = getApiErrorMessage(error, localization.error.automationCreate)
      showToast(message, 'error', { timeout: false })
    }
  }
</script>