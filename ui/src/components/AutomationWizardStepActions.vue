<template>
  <div class="automation-wizard-step-actions">
    <keep-alive>
      <template v-for="(action, index) in actions" :key="index">
        <AutomationWizardAction :action :automation :index @update:action="updateAction(index, $event)" @delete="removeAction(index)" />
        <p-divider />
      </template>
    </keep-alive>

    <template v-if="actionsError">
      <p-message error>
        {{ actionsError }}
      </p-message>
    </template>

    <p-button class="automations-wizard-step-actions__add" icon="PlusIcon" @click="addAction">
      Add Action
    </p-button>
  </div>
</template>

<script lang="ts" setup>
  import { useWizardStep } from '@prefecthq/prefect-design'
  import { AutomationAction, isAutomationAction } from '@prefecthq/prefect-ui-library'
  import { useValidation, useValidationObserver } from '@prefecthq/vue-compositions'
  import { onMounted, reactive, watch } from 'vue'
  import AutomationWizardAction from '@/components/AutomationWizardAction.vue'
  import { AutomationActionFormValues } from '@/types/automation'

  const props = defineProps<{
    automation: AutomationActionFormValues,
  }>()

  const emit = defineEmits<{
    (event: 'update:automation', value: AutomationActionFormValues): void,
  }>()

  const actions = reactive<Partial<AutomationAction>[]>(props.automation.actions ?? [])

  function addAction(): void {
    actions.push({})
  }

  function removeAction(index: number): void {
    actions.splice(index, 1)
  }

  function updateAction(index: number, action: Partial<AutomationAction>): void {
    actions[index] = action
  }

  const { error: actionsError } = useValidation(actions, 'Actions', value => {
    if (value.length) {
      return true
    }

    return 'At least 1 action is required'
  })

  const { defineValidate } = useWizardStep()
  const { validate } = useValidationObserver()

  defineValidate(validate)

  onMounted(() => {
    if (actions.length === 0) {
      addAction()
    }
  })

  watch(actions, () => {
    emit('update:automation', {
      ...props.automation,
      actions: actions.filter(isAutomationAction),
    })
  })
</script>

<style>
.automation-wizard-step-actions { @apply
  grid
  gap-8
}

.automations-wizard-step-actions__add { @apply
  justify-self-start
}
</style>
