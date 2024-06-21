<template>
  <p-content class="automation-wizard-step-details">
    <p-label label="Automation Name" :state :message>
      <template #default="{ id }">
        <p-text-input :id v-model="name" :state />
      </template>
    </p-label>
    <p-label label="Description (Optional)">
      <template #default="{ id }">
        <p-text-input :id v-model="description" />
      </template>
    </p-label>
  </p-content>
</template>

<script lang="ts" setup>
  import { useWizardStep } from '@prefecthq/prefect-design'
  import { usePatchRef, useValidation, useValidationObserver, ValidationRule } from '@prefecthq/vue-compositions'
  import { AutomationFormValues } from '@/types/automation'

  const automation = defineModel<AutomationFormValues>('automation', { required: true })

  const name = usePatchRef(automation, 'name')
  const description = usePatchRef(automation, 'description')

  const { validate } = useValidationObserver()

  const isRequired: ValidationRule<string | undefined> = (value = '', label) => {
    if (value.length > 0) {
      return true
    }

    return `${label} is required`
  }

  const { state, error: message } = useValidation(name, 'Automation name', isRequired)


  const { defineValidate } = useWizardStep()

  defineValidate(validate)
</script>