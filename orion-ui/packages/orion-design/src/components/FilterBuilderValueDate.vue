<template>
  <div class="filter-builder-value-date">
    <m-select v-model="internalOperation" :options="operations" />
    <m-input v-model="internalValue" label="Text" />
  </div>
</template>

<script lang="ts" setup>
  import { computed, onMounted } from 'vue'
  import { FilterOperation, FilterType, FilterValue } from '../types/filters'

  // eslint really doesn't like defineEmits type annotation syntax
  // eslint-disable-next-line func-call-spacing
  const emit = defineEmits<{
    // eslint-disable-next-line no-unused-vars
    (event: 'update:type', value: FilterType): void,
    // eslint-disable-next-line no-unused-vars
    (event: 'update:operation', value: FilterOperation): void,
    // eslint-disable-next-line no-unused-vars
    (event: 'update:value', value: FilterValue): void,
  }>()

  const props = defineProps<{
    type?: FilterType,
    operation?: FilterOperation,
    value?: FilterValue,
  }>()

  onMounted(() => {
    if (props.operation === undefined) {
      internalOperation.value = 'after'
    }
  })

  const internalOperation = computed({
    get: () => props.operation,
    set: (operation) => {
      emit('update:operation', operation!)

      if (operation == 'before' || operation == 'after') {
        internalType.value = 'date'
      }

      if (operation == 'newer' || operation == 'older') {
        internalType.value = 'time'
      }
    },
  })

  const internalType = computed({
    get: () => props.type,
    set: (type) => emit('update:type', type!),
  })

  const internalValue = computed({
    get: () => props.value,
    set: (value) => emit('update:value', value!),
  })

  const operations = [
    { label: 'Before', value: 'before' },
    { label: 'After', value: 'after' },
    { label: 'Newer', value: 'newer' },
    { label: 'Older', value: 'older' },
  ]
</script>

<style lang="scss" scoped>
.filter-builder-value-date {
  display: grid;
  gap: var(--m-1);
  grid-template-columns: minmax(100px, 370px) minmax(100px, 1fr);
  align-items: flex-end;
}
</style>