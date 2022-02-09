<template>
  <component
    :is="component"
    v-model:type="internalType"
    v-model:operation="internalOperation"
    v-model:value="internalValue"
    :property="property"
  />
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import { FilterOperation, FilterProperty, FilterType, FilterValue } from '../types/filters'
  import FilterBuilderValueDate from './FilterBuilderValueDate.vue'
  import FilterBuilderValueState from './FilterBuilderValueState.vue'
  import FilterBuilderValueString from './FilterBuilderValueString.vue'
  import FilterBuilderValueTag from './FilterBuilderValueTag.vue'

  const emit = defineEmits<{
    (event: 'update:type', value: FilterType): void,
    (event: 'update:operation', value: FilterOperation): void,
    (event: 'update:value', value: FilterValue): void,
  }>()

  const props = defineProps<{
    property: FilterProperty,
    type?: FilterType,
    operation?: FilterOperation,
    value?: FilterValue,

  }>()

  // eslint-disable-next-line vue/return-in-computed-property
  const component = computed(() => {
    // eslint-disable-next-line default-case
    switch (props.property) {
      case 'tag':
        return FilterBuilderValueTag
      case 'name':
        return FilterBuilderValueString
      case 'start_date':
        return FilterBuilderValueDate
      case 'state':
        return FilterBuilderValueState
    }
  })

  const internalType = computed({
    get: () => props.type,
    set: (type) => emit('update:type', type!),
  })

  const internalOperation = computed({
    get: () => props.operation,
    set: (operation) => emit('update:operation', operation!),
  })

  const internalValue = computed({
    get: () => props.value,
    set: (value) => emit('update:value', value!),
  })
</script>