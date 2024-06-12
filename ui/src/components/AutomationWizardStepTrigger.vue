<template>
  <p-content class="automation-wizard-step-trigger">
    <p-label label="Trigger Template" :state :message>
      <template #default="{ id }">
        <AutomationTriggerTemplateSelect :id v-model:template="template" :state />
      </template>
    </p-label>

    <template v-if="input">
      <p-button-group class="automation-wizard-step-trigger__mode-switcher" :model-value="mode" :options="formMode" small @update:model-value="switchMode($event)" />

      <template v-if="mode === 'Form' && template">
        <component :is="input.component" :key="template" v-bind="input.props" />
      </template>

      <template v-else-if="mode === 'JSON'">
        <AutomationTriggerJsonInput v-model="jsonString" />
      </template>
    </template>
  </p-content>
</template>

<script lang="ts" setup>
  import { useWizardStep } from '@prefecthq/prefect-design'
  import { createTuple, stringify, withProps, AutomationTriggerEventInput, AutomationTrigger, AutomationTriggerResponse, getAutomationTriggerTemplate, getDefaultAutomationTriggerValue, isNullish, AutomationTriggerCustomInput } from '@prefecthq/prefect-ui-library'
  import { useValidation, useValidationObserver } from '@prefecthq/vue-compositions'
  import { computed, ref, watch } from 'vue'
  import AutomationTriggerJsonInput from '@/components/AutomationTriggerJsonInput.vue'
  import AutomationTriggerTemplateSelect from '@/components/AutomationTriggerTemplateSelect.vue'
  import { mapper } from '@/services/mapper'
  import { AutomationFormValues } from '@/types/automation'

  const automation = defineModel<AutomationFormValues>('automation', { required: true })

  const template = computed({
    get() {
      if (automation.value.trigger) {
        return getAutomationTriggerTemplate(automation.value.trigger)
      }

      return null
    },
    set(template) {
      if (isNullish(template)) {
        updateTrigger(undefined)
        return
      }

      updateTrigger(getDefaultAutomationTriggerValue(template))
    },
  })

  const { values: formMode } = createTuple(['Form', 'JSON'])
  type FormMode = typeof formMode[number]
  const mode = ref<FormMode>('Form')

  function triggerAsJsonString(): string {
    const triggerMatchingApi = mapper.map('AutomationTrigger', automation.value.trigger, 'AutomationTriggerRequest')

    return stringify(triggerMatchingApi)
  }

  const jsonString = ref<string>(triggerAsJsonString())

  watch(() => automation.value.trigger, () => jsonString.value = triggerAsJsonString())

  function updateTriggerFromJsonString(): AutomationTrigger {
    const parsedTriggerJson: AutomationTriggerResponse = JSON.parse(jsonString.value)
    const trigger = mapper.map('AutomationTriggerResponse', parsedTriggerJson, 'AutomationTrigger')
    updateTrigger(trigger)

    return trigger
  }

  async function switchMode(newMode: FormMode): Promise<void> {
    if (mode.value === newMode) {
      return
    }

    if (!await validate()) {
      return
    }

    if (newMode === 'Form') {
      updateTriggerFromJsonString()
    }

    if (newMode === 'JSON') {
      jsonString.value = triggerAsJsonString()
    }

    mode.value = newMode
  }


  const { defineValidate } = useWizardStep()
  const { validate } = useValidationObserver()
  const { state, error: message } = useValidation(template, 'Trigger template', value => {
    if (value) {
      return true
    }

    return 'Trigger type is required'
  })

  defineValidate(async () => {
    const valid = await validate()

    if (valid) {
      // In form mode, the trigger is kept in sync with the form component's values,
      // but in JSON mode, we'll sync on submit so that the input can be freely
      // updated without affecting the form state. Also delay (de)serialization
      // to submit rather than on every change.
      if (mode.value === 'JSON') {
        updateTriggerFromJsonString()
      }
    }
    return valid
  })

  const input = computed(() => {
    if (!template.value) {
      return null
    }

    const trigger = automation.value.trigger ?? getDefaultAutomationTriggerValue(template.value)

    switch (trigger.type) {
      case 'event':
        return withProps(AutomationTriggerEventInput, {
          template: template.value,
          trigger,
          'onUpdate:trigger': updateTrigger,
        })
      case 'compound':
      case 'sequence':
        return withProps(AutomationTriggerCustomInput, {
          trigger,
          'onUpdate:trigger': updateTrigger,
        })

      default:
        const exhaustive: never = trigger
        throw new Error(`AutomationWizardStepTrigger is missing case for trigger type ${(exhaustive as AutomationTrigger).type}`)
    }

  })

  function updateTrigger(trigger: AutomationTrigger | undefined): void {
    automation.value = {
      ...automation.value,
      trigger,
    }
  }
</script>

<style>
.automation-wizard-step-trigger__mode-switcher { @apply
  mx-auto
}
</style>