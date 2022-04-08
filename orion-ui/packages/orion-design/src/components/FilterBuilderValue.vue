<template>
  <component
    :is="component"
    v-model:operation="filter.operation"
    v-model:value="filter.value"
    :object="filter.object"
    :property="filter.property"
  />
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import FilterBuilderValueDate from '@/components/FilterBuilderValueDate.vue'
  import FilterBuilderValueState from '@/components/FilterBuilderValueState.vue'
  import FilterBuilderValueString from '@/components/FilterBuilderValueString.vue'
  import FilterBuilderValueTag from '@/components/FilterBuilderValueTag.vue'
  import { Filter } from '@/types/filters'

  const emit = defineEmits<{
    (event: 'update:filter', value: Partial<Filter>): void,
  }>()

  const props = defineProps<{
    filter: Partial<Filter>,
  }>()

  const filter = computed({
    get() {
      return props.filter
    },
    set(filter: Partial<Filter>) {
      emit('update:filter', filter)
    },
  })

  const component = computed(() => {
    switch (filter.value.property) {
      case 'tag':
        return FilterBuilderValueTag
      case 'name':
        return FilterBuilderValueString
      case 'start_date':
        return FilterBuilderValueDate
      case 'state':
        return FilterBuilderValueState
      default:
        return null
    }
  })
</script>