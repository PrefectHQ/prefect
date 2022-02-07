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

  // eslint really doesn't like defineEmits type annotation syntax
  // eslint-disable-next-line func-call-spacing
  const emit = defineEmits<{
    // eslint-disable-next-line no-unused-vars
    (event: 'update:operation', value: FilterOperation): void,
    // eslint-disable-next-line no-unused-vars
    (event: 'update:value', value: FilterValue): void,
  }>()

  const props = defineProps<{
    value?: string[],
  }>()

  onMounted(() => {
    emit('update:operation', 'or')
  })

  const internalValue = computed({
    get: () => props.value,
    set: (value) => emit('update:value', value!),
  })

  const states: { label: string, value: Lowercase<StateType> }[] = [
    { label: 'Scheduled', value: 'scheduled' },
    { label: 'Pending', value: 'pending' },
    { label: 'Running', value: 'running' },
    { label: 'Completed', value: 'completed' },
    { label: 'Failed', value: 'failed' },
    { label: 'Cancelled', value: 'cancelled' },
  ]

  function isChecked(value: Lowercase<StateType>): boolean {
    return (props.value ?? []).includes(value)
  }

  function toggle(value: Lowercase<StateType>): void {
    const values = props.value ?? []
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