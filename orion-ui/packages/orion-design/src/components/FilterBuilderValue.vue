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

<style lang="scss" scoped></style>