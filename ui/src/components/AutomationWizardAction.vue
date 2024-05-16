<template>
  <div class="automation-wizard-action">
    <div class="automation-wizard-action__header">
      <span class="automation-wizard-action__heading">Action {{ index + 1 }}</span>
      <p-button size="sm" icon="TrashIcon" @click="emit('delete')" />
    </div>

    <p-content>
      <p-label label="Action Type" :state :message>
        <template #default="{ id }">
          <AutomationActionTypeSelect :id v-model:type="type" :state />
        </template>
      </p-label>


      <template v-if="input">
        <component :is="input.component" v-bind="input.props" @update:action="updateAction" />
      </template>
    </p-content>
  </div>
</template>

<script lang="ts" setup>
  import { withProps, AutomationActionInput, AutomationAction, isNullish, getAutomationTriggerTemplate, getDefaultValueForAction } from '@prefecthq/prefect-ui-library'
  import { useValidation } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import AutomationActionTypeSelect from '@/components/AutomationActionTypeSelect.vue'
  import { AutomationActionFormValues } from '@/types/automation'

  const props = defineProps<{
    index: number,
    action: Partial<AutomationAction>,
    automation: AutomationActionFormValues,
  }>()

  const emit = defineEmits<{
    (event: 'delete'): void,
    (event: 'update:action', value: Partial<AutomationAction>): void,
  }>()

  const type = computed({
    get() {
      return props.action.type ?? null
    },
    set(value) {
      if (isNullish(value)) {
        emit('update:action', {})
        return
      }

      const template = getAutomationTriggerTemplate(props.automation.trigger)
      const action = getDefaultValueForAction(value, template)

      emit('update:action', action)
    },
  })

  const { state, error: message } = useValidation(type, 'Action Type', value => !!value)

  const input = computed(() => {
    if (!props.action.type) {
      return null
    }

    return withProps(AutomationActionInput, {
      action: props.action,
      'onUpdate:action': value => emit('update:action', value),
    })
  })

  function updateAction(action: Partial<AutomationAction>): void {
    emit('update:action', action)
  }
</script>

<style>
.automation-wizard-action { @apply
  grid
  gap-1
}

.automation-wizard-action__header { @apply
  flex
  items-center
  justify-between
}

.automation-wizard-action__heading { @apply
  font-bold
}
</style>