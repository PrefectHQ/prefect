<template>
  <div class="filter-builder-value-state">
    <template v-for="state in states" :key="state.value">
      <m-checkbox :model-value="isChecked(state.value)" @change="toggle(state.value)">
        {{ state.label }}
      </m-checkbox>
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { computed, onMounted } from 'vue'
  import { StateType } from '../models/StateType'
  import { FilterOperation, FilterValue } from '../types/filters'

  const emit = defineEmits<{
    (event: 'update:operation', value: FilterOperation): void,
    (event: 'update:value', value: FilterValue): void,
  }>()

  const props = defineProps<{
    value?: FilterValue,
    // used for a v-model but not referenced directly
    // eslint-disable-next-line vue/no-unused-properties
    operation?: FilterOperation,
  }>()

  onMounted(() => {
    if (props.value === undefined) {
      internalValue.value = []
    }

    emit('update:operation', 'or')
  })

  const internalValue = computed({
    get: () => Array.isArray(props.value) ? props.value : [],
    set: (value) => emit('update:value', value!),
  })

  const states: { label: string, value: StateType }[] = [
    { label: 'Scheduled', value: 'SCHEDULED' },
    { label: 'Pending', value: 'PENDING' },
    { label: 'Running', value: 'RUNNING' },
    { label: 'Completed', value: 'COMPLETED' },
    { label: 'Failed', value: 'FAILED' },
    { label: 'Cancelled', value: 'CANCELLED' },
  ]

  function isChecked(value: StateType): boolean {
    return internalValue.value.includes(value)
  }

  function toggle(value: StateType): void {
    const values = internalValue.value
    const index = values.indexOf(value)

    if (index >= 0) {
      values.splice(index, 1)
    } else {
      values.push(value)
    }

    internalValue.value = values
  }
</script>

<style lang="scss" scoped>
.filter-builder-value-state {
  display: grid;
  gap: var(--m-1);
  grid-template-columns: repeat( auto-fit, minmax(120px, 1fr) );
  align-items: flex-end;
}
</style>