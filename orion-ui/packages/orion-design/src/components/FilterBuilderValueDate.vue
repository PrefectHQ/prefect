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
        <m-number-input v-model="count" class="filter-builder-value-date__number" />
      </div>
    </template>
  </div>
</template>

<script lang="ts" setup>
  import isDate from 'date-fns/isDate'
  import startOfToday from 'date-fns/startOfToday'
  import { Ref, computed, onMounted, watch } from 'vue'
  import { FilterOperation, FilterType, FilterValue, FilterObject } from '../types/filters'
  import { toPluralString } from '../utilities'
  import DateTimeInput from './DateTimeInput.vue'

  const emit = defineEmits<{
    (event: 'update:type', value: FilterType): void,
    (event: 'update:operation', value: FilterOperation): void,
    (event: 'update:value', value: FilterValue): void,
  }>()

  const props = defineProps<{
    object: FilterObject,
    operation?: FilterOperation,
    value?: FilterValue,
  }>()

  onMounted(() => {
    if (props.operation === undefined) {
      internalOperation.value = 'after'
    }
  })

  watch(() => props.operation, () => {
    if (props.operation == 'newer' || props.operation == 'older' || props.operation == 'upcoming' && typeof props.value !== 'string') {
      emit('update:value', '1h')
    } else if (props.operation == 'after' || props.operation == 'before' && !isDate(props.value)) {
      emit('update:value', startOfToday())
    }
  })

  const internalOperation = computed({
    get: () => props.operation,
    set: (operation) => {
      emit('update:operation', operation!)
    },
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
  const operations = computed(() => {
    const base = [
      { label: 'Newer than', value: 'newer' },
      { label: 'Before date', value: 'before' },
      { label: 'After date', value: 'after' },
      { label: 'Older than', value: 'older' },
    ]

    if (props.object == 'flow_run') {
      base.push({ label: 'Upcoming within', value: 'upcoming' })
    }

    return base
  })

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
  display: flex;
  gap: var(--m-2);
  align-items: flex-end;
}

.filter-builder-value-date__relative {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: inherit;
  flex-grow: 1;
  min-width: 200px;
}

.filter-builder-value-date__number :deep(.number-input__container) {
  height: 58px;
}

.filter-builder-value-date__number :deep(.number-input__spin-buttons) {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding-top: 0;
}
</style>