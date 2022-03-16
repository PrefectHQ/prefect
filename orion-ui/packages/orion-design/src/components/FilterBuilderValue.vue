<template>
  <component
    :is="component"
    v-model:operation="internalOperation"
    v-model:value="internalValue"
    v-bind="{ object, property }"
  />
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import FilterBuilderValueDate from '@/components/FilterBuilderValueDate.vue'
  import FilterBuilderValueState from '@/components/FilterBuilderValueState.vue'
  import FilterBuilderValueString from '@/components/FilterBuilderValueString.vue'
  import FilterBuilderValueTag from '@/components/FilterBuilderValueTag.vue'
  import { FilterObject, FilterOperation, FilterProperty, FilterValue } from '@/types/filters'

  const emit = defineEmits<{
    (event: 'update:operation', value: FilterOperation): void,
    (event: 'update:value', value: FilterValue): void,
  }>()

  const props = defineProps<{
    object: FilterObject,
    property: FilterProperty,
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

  const internalOperation = computed({
    get: () => props.operation,
    set: (operation) => emit('update:operation', operation!),
  })

  const internalValue = computed({
    get: () => props.value,
    set: (value) => emit('update:value', value!),
  })
</script>