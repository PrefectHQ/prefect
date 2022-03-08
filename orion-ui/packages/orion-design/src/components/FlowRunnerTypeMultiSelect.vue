<template>
  <div class="flow-runner-types-multi-select">
    <template v-for="option in flowRunners" :key="option.value">
      <LabelWrapper :label="option.label" class="flow-runner-types-multi-select__option">
        <m-checkbox
          :value="selectedFlowRunnerTypes.includes(option.value)"
          :label="option.label"
          class="flow-runner-types-multi-select__checkbox"
          @update:model-value="updateSelected(option.value, $event)"
        />
      </LabelWrapper>
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { PropType } from 'vue'
  import LabelWrapper from '@/components/LabelWrapper.vue'
  import { FlowRunnerType } from '@/types/FlowRunnerType'

  const flowRunners: { label: string, value: FlowRunnerType }[] = [
    { label: 'Universal', value: 'universal' },
    { label: 'Kubernetes', value: 'kubernetes' },
    { label: 'Docker', value: 'docker' },
    { label: 'Subprocess', value: 'subprocess' },
  ]

  const props = defineProps({
    selectedFlowRunnerTypes: {
      type: Array as PropType<FlowRunnerType[]>,
      default: () => [],
    },
  })

  const emit = defineEmits<{
    (event: 'update:selectedFlowRunnerTypes', value: string[]): void,
  }>()

  const updateSelected = (flowRunnerType: FlowRunnerType, selected: boolean): void => {
    if (selected && !props.selectedFlowRunnerTypes.includes(flowRunnerType)) {
      emit('update:selectedFlowRunnerTypes', [...props.selectedFlowRunnerTypes, flowRunnerType])
    } else if (!selected && props.selectedFlowRunnerTypes.includes(flowRunnerType)) {
      emit('update:selectedFlowRunnerTypes', [...props.selectedFlowRunnerTypes].filter(type => type !== flowRunnerType))
    }
  }
</script>

<style lang="scss">
.flow-runner-types-multi-select {
  display: flex;
  flex-direction: row;
  margin-left: 0px;
}

.flow-runner-types-multi-select__option{
  text-align: center;
}

.flow-runner-types-multi-select__checkbox {
  margin-left: 0px;
}
</style>