<template>
  <div class="filter-builder-value-tag">
    <m-input v-model="input" placeholder="Press enter to add tag" @keydown.prevent.enter="add" />
  </div>
</template>

<script lang="ts" setup>
  import { ref, computed, onMounted } from 'vue'
  import { FilterOperation, FilterValue } from '../types/filters'

  // eslint really doesn't like defineEmits type annotation syntax
  // eslint-disable-next-line func-call-spacing
  const emit = defineEmits<{
    // eslint-disable-next-line no-unused-vars
    (event: 'update:operation', value: FilterOperation): void,
    // eslint-disable-next-line no-unused-vars
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

    const values = internalValue.value

    internalValue.value.push(input.value.trim())

    internalValue.value = values
    input.value = ''
  }
</script>

<style lang="scss" scoped>
.filter-builder-value-tag {
}
</style>