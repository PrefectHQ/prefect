<template>
  <p-message info>
    Custom triggers allow advanced configuration of the conditions on which a trigger executes its actions.

    <template #action>
      <DocumentationButton :to="localization.docs.automationTriggers" small />
    </template>
  </p-message>

  <p-label label="Trigger" :state="state" :message="error">
    <JsonInput v-model="model" class="automation-trigger-json-input__json-input" show-format-button :state="state" />
  </p-label>
</template>

<script setup lang="ts">
  import { DocumentationButton, JsonInput, isEmptyArray, isEmptyString, isInvalidDate, isNullish, localization } from '@prefecthq/prefect-ui-library'
  import { ValidationRule, useValidation } from '@prefecthq/vue-compositions'
  import { mapper } from '@/services/mapper'

  const model = defineModel<string>({ required: true })

  const isMappableAutomationTriggerJson: ValidationRule<string> = (value) => {
    try {
      const json = JSON.parse(value)

      mapper.map('AutomationTriggerResponse', json, 'AutomationTrigger')
    } catch (error) {
      return false
    }

    return true
  }

  const isRequired: ValidationRule<unknown> = (value, name) => {
    if (isNullish(value) || isEmptyArray(value) || isEmptyString(value) || isInvalidDate(value)) {
      return `${name} is required`
    }

    return true
  }

  const isJson: ValidationRule<string> = (value, name) => {
    try {
      JSON.parse(value)
    } catch {
      return `${name} must be valid JSON`
    }

    return true
  }

  const { state, error } = useValidation(model, 'Trigger', [isRequired, isJson, isMappableAutomationTriggerJson])
</script>

<style>
.automation-trigger-json-input__json-input {
  min-height: 400px;
}
</style>