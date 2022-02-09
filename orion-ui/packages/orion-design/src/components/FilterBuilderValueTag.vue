<template>
  <div class="filter-builder-value-tag">
    <m-input v-model="input" placeholder="Press enter to add tag" @keydown.prevent.enter="add" />
  </div>
</template>

<script lang="ts" setup>
  import { ref, computed, onMounted } from 'vue'
  import { FilterOperation, FilterValue } from '../types/filters'

  const emit = defineEmits<{
    (event: 'update:operation', value: FilterOperation): void,
    (event: 'update:value', value: FilterValue): void,
  }>()

  const props = defineProps<{
    value?: FilterValue,
  }>()

  onMounted(() => {
    emit('update:operation', 'and')
  })

  const internalValue = computed({
    get: () => Array.isArray(props.value) ? props.value : [],
    set: (value) => emit('update:value', value!),
  })


  const input = ref('')

  function add(): void {
    if (input.value === '') {
      return
    }

    internalValue.value  = [...internalValue.value, input.value.trim()]
    input.value = ''
  }
</script>