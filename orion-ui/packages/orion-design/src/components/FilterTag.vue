<template>
  <DismissibleTag v-bind="{ label, dismissible }" class="filter-tag" @dismiss="dismiss(filter)" />
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import { FilterService } from '../services/FilterService'
  import { Filter } from '../types/filters'
  import DismissibleTag from './DismissibleTag.vue'

  // eslint really doesn't like defineEmits type annotation syntax
  // eslint-disable-next-line func-call-spacing
  const emit = defineEmits<{
    // eslint-disable-next-line no-unused-vars
    (event: 'dismiss', filter: Required<Filter>): void,
  }>()

  type Props = {
    filter: Required<Filter>,
    dismissible?: boolean,
  }

  const props = defineProps<Props>()

  const label = computed<string>(() => FilterService.stringify(props.filter))

  function dismiss(filter: Required<Filter>): void {
    if (props.dismissible) {
      emit('dismiss', filter)
    }
  }
</script>