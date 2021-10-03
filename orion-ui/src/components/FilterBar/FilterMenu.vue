<template>
  <Card class="menu font--primary" tabindex="0">
    <div class="menu-content"> HELLO IM A FILTER MENU </div>
  </Card>
</template>

<script lang="ts" setup>
import { computed, defineEmits, defineProps } from 'vue'

const emit = defineEmits(['update:modelValue', 'close'])
// const props = defineProps<{
//   modelValue: string
//   options: { label: string; value: string }[]
// }>()

// const value = computed(() => {
//   return props.modelValue
// })

// const selectOption = (val: string) => {
//   emit('update:modelValue', val)
//   emit('close')
// }
</script>

<style lang="scss" scoped>
.menu {
  height: auto;
  width: 100%;
  border-radius: 0;

  .menu-content {
    border-top: 2px solid $grey-10;
  }

  ::v-deep(*) {
    border-radius: 0 0 3px 3px !important;
  }
}
</style>
