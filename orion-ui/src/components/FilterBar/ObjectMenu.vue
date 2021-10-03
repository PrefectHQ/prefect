<template>
  <Card class="menu font--primary" miter shadow="sm" tabindex="0">
    <button
      v-for="option in props.options"
      :key="option.value"
      class="
        option
        pa-2
        text-left text--grey-80
        d-flex
        align-center
        justify-space-between
      "
      :class="{ active: option.value == value }"
      @click="selectOption(option.value)"
    >
      {{ option.label }}
      <i v-if="option.value == value" class="pi pi-check-line" />
    </button>
  </Card>
</template>

<script lang="ts" setup>
import { computed, defineEmits, defineProps } from 'vue'

const emit = defineEmits(['update:modelValue', 'close'])
const props = defineProps<{
  modelValue: string
  options: { label: string; value: string }[]
}>()

const value = computed(() => {
  return props.modelValue
})

const selectOption = (val: string) => {
  emit('update:modelValue', val)
  emit('close')
}
</script>

<style lang="scss" scoped>
.menu {
  .option {
    background-color: $white;
    border: none;
    border-bottom: 2px solid $grey-10;
    outline: none;
    min-height: 58px;
    min-width: 200px;

    &:focus {
      background-color: $grey-10;
    }

    &:hover {
      background-color: $primary;
      color: $white !important;
      cursor: pointer;
    }

    &:active {
      background-color: $primary !important;
      color: $white !important;
    }

    &:last-of-type {
      border-bottom: none;
    }

    &.active {
      background-color: $primary;
      color: $white !important;
    }
  }
}
</style>
