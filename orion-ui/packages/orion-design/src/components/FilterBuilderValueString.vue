<template>
  <div class="filter-builder-value-string">
    <!-- <m-select v-model="internalOperation" :options="operations" /> -->
    <m-input v-model="internalValue" label="Text" />
  </div>
</template>

<script lang="ts" setup>
  import { computed, onMounted } from 'vue'
  import { FilterOperation, FilterValue } from '../types/filters'

  const emit = defineEmits<{
    (event: 'update:operation', value: FilterOperation): void,
    (event: 'update:value', value: FilterValue): void,
  }>()

  const props = defineProps<{
    operation?: FilterOperation,
    value?: FilterValue,
  }>()

  onMounted(() => {
    if (props.operation === undefined) {
      internalOperation.value = 'equals'
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
  grid-template-columns: minmax(100px, 350px) minmax(100px, 1fr);
  align-items: flex-end;
}
</style>