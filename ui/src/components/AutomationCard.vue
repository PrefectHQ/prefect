<template>
  <p-card class="automation-card">
    <p-content>
      <p-content secondary>
        <div class="automation-card__header">
          <p-link class="automation-card__name" :to="routes.automation(automation.id)">
            {{ automation.name }}
          </p-link>
          <div class="automation-card__header-actions">
            <AutomationToggle :automation="automation" @update="emit('update')" />
            <AutomationMenu :automation="automation" @delete="emit('update')" />
          </div>
        </div>
        <template v-if="automation.description">
          <p class="automation-card__description">
            {{ automation.description }}
          </p>
        </template>
      </p-content>

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
  </p-card>
</template>

<script lang="ts" setup>
  import { toPluralString } from '@prefecthq/prefect-design'
  import { AutomationMenu, AutomationToggle, AutomationTriggerDescription, AutomationActionDescription, useWorkspaceRoutes } from '@prefecthq/prefect-ui-library'
  import { Automation } from '@/types/automation'

  defineProps<{
    automation: Automation,
  }>()

  const emit = defineEmits<{
    (event: 'update'): void,
  }>()

  const routes = useWorkspaceRoutes()
</script>

<style>
.automation-card__header { @apply
  flex
  gap-2
  items-center
  justify-between
}

.automation-card__header-actions { @apply
  flex
  gap-2
  items-center
}

.automation-card__name { @apply
  text-lg
}

.automation-card__description { @apply
  text-sm
}

.automation-card__label { @apply
  font-medium
  mr-2
}
</style>