<template>
  <div class="filter-builder-value-date">
    <m-select v-model="internalOperation" :options="operations" />
    <template v-if="isDateFilter">
      <DateTimeInput v-model:value="date" label="Date" />
    </template>
    <template v-else>
      <div class="filter-builder-value-date__relative">
        <m-select v-model="unit" :options="units">
          <template #selected-option-label="{ label }">
            {{ toPluralString(label, count) }}
          </template>
          <template #option-label="{ label }">
            {{ toPluralString(label, count) }}
          </template>
        </m-select>
        <m-number-input v-model="count" min="1" />
      </div>
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { Ref, computed, onMounted } from 'vue'
  import { FilterOperation, FilterType, FilterValue } from '../types/filters'
  import { toPluralString } from '../utilities'
  import DateTimeInput from './DateTimeInput.vue'

  const emit = defineEmits<{
    (event: 'update:type', value: FilterType): void,
    (event: 'update:operation', value: FilterOperation): void,
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

  const unit: Ref<string> = computed<string>({
    get: () => {
      if (typeof props.value !== 'string') {
        return 'h'
      }

      const lastCharacter = props.value.slice(-1)
      return lastCharacter
    },
    set: (unit) => emit('update:value', `${count.value}${unit}`),
  })

  const count: Ref<number> = computed<number>({
    get: () => {
      if (typeof props.value !== 'string') {
        return 1
      }

      return parseInt(props.value)
    },
    set: (count) => emit('update:value', `${count}${unit.value}`),
  })


  const date: Ref<Date | null> = computed<Date | null>({
    get: () => {
      if (props.value instanceof Date) {
        return props.value
      }

      return null
    },
    set: (date) => emit('update:value', date!),
  })

  const isDateFilter = computed<boolean>(() => props.operation == 'before' || props.operation == 'after')

  const operations = [
    { label: 'Before', value: 'before' },
    { label: 'After', value: 'after' },
    { label: 'Newer', value: 'newer' },
    { label: 'Older', value: 'older' },
  ]

  const units = [
    { label: 'Hour', value: 'h' },
    { label: 'Day', value: 'd' },
    { label: 'Week', value: 'w' },
    { label: 'Month', value: 'm' },
    { label: 'Year', value: 'y' },
  ]
</script>

<style lang="scss" scoped>
.filter-builder-value-date {
  display: grid;
  gap: var(--m-2);
  align-items: flex-end;
  grid-template-columns: minmax(100px, 350px) minmax(100px, 1fr);
}

.filter-builder-value-date__relative {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: inherit;
}
</style>