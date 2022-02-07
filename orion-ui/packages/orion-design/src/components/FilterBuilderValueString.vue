<template>
  <div class="filter-builder-value-string">
    <m-select v-model="internalOperation" :options="operations" />
    <m-input v-model="internalValue" label="Text" />
  </div>
</template>

<script lang="ts" setup>
  import { computed, onMounted } from 'vue'
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
    operation?: FilterOperation,
    value?: FilterValue,
  }>()

  onMounted(() => {
    if (props.operation === undefined) {
      internalOperation.value = 'contains'
    }
  })

  const internalOperation = computed({
    get: () => props.operation,
    set: (operation) => emit('update:operation', operation!),
  })

  const internalValue = computed({
    get: () => props.value,
    set: (value) => emit('update:value', value!),
  })

  const operations = [
    { label: 'Contains', value: 'contains' },
    { label: 'Equals', value: 'equals' },
  ]
</script>

<style lang="scss" scoped>
.filter-builder-value-string {
  display: grid;
  gap: var(--m-1);
  grid-template-columns: minmax(100px, 370px) minmax(100px, 1fr);
  align-items: flex-end;
}
</style>