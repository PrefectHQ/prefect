<template>
  <DismissibleTag v-bind="{ label, dismissible }" class="filter-tag" @dismiss="dismiss(filter)" />
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import DismissibleTag from '@/components/DismissibleTag.vue'
  import { FilterService } from '@/services/FilterService'
  import { Filter } from '@/types/filters'

  const emit = defineEmits<{
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