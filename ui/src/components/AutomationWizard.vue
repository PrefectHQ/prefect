<template>
  <p-wizard
    ref="wizardRef"
    class="automation-wizard"
    :steps="steps"
    :last-step-text="lastStepText"
    show-cancel
    :nonlinear="editing"
    :show-save-and-exit="editing"
    @cancel="cancel"
    @submit="submit"
  >
    <template #trigger-step>
      <AutomationWizardStepTrigger v-model:automation="automation" />
    </template>
    <template #actions-step>
      <template v-if="isAutomationActionFormValues(automation)">
        <AutomationWizardStepActions v-model:automation="automation" />
      </template>
    </template>
    <template #details-step>
      <AutomationWizardStepDetails v-model:automation="automation" />
    </template>
  </p-wizard>
</template>

<script lang="ts" setup>
  import { PWizard, WizardStep } from '@prefecthq/prefect-design'
  import { computed, ref } from 'vue'
  import { useRouter } from 'vue-router'
  import AutomationWizardStepActions from '@/components/AutomationWizardStepActions.vue'
  import AutomationWizardStepDetails from '@/components/AutomationWizardStepDetails.vue'
  import AutomationWizardStepTrigger from '@/components/AutomationWizardStepTrigger.vue'
  import { Automation, AutomationFormValues, IAutomation, isAutomationActionFormValues } from '@/types/automation'

  const props = defineProps<{
    automation?: Partial<Automation>,
    editing?: boolean,
  }>()

  const automation = ref<AutomationFormValues>(props.automation ?? {})

  const emit = defineEmits<{
    (event: 'submit', value: Automation): void,
  }>()

  const router = useRouter()

  const lastStepText = computed(() => props.automation ? 'Save' : 'Create')

  const steps: WizardStep[] = [
    { title: 'Trigger', key: 'trigger-step' },
    { title: 'Actions', key: 'actions-step' },
    { title: 'Details', key: 'details-step' },
  ]

  const wizardRef = ref<InstanceType<typeof PWizard>>()

  function submit(): void {
    emit('submit', new Automation(automation.value as IAutomation))
  }

  function cancel(): void {
    router.back()
  }
</script>