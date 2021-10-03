<template>
  <Card class="timeframe-menu" tabindex="0">
    <div class="menu-content pa-2"> TIMEFRAME MENU </div>
  </Card>
</template>

<script lang="ts" setup>
// import { computed, defineEmits, defineProps, ref } from 'vue'

// const emit = defineEmits(['update:modelValue', 'close'])
// // const props = defineProps<{
// //   modelValue: string
// //   options: { label: string; value: string }[]
// // }>()

// // const value = computed(() => {
// //   return props.modelValue
// // })

// const states = ref<{ name: string; value: string; checked: boolean }[]>([
//   { name: 'Scheduled', value: 'SCHEDULED', checked: false },
//   { name: 'Pending', value: 'PENDING', checked: false },
//   { name: 'Running', value: 'RUNNING', checked: false },
//   { name: 'Completed', value: 'COMPLETED', checked: false },
//   { name: 'Failed', value: 'FAILED', checked: false },
//   { name: 'Cancelled', value: 'CANCELLED', checked: false }
//   //   { name: 'Awaiting Retry', value: '' },
//   //   { name: 'Retrieved Cache', value: 'SCHEDULED' },
//   //   { name: 'Crashed', value: 'CRASHED' },
// ])

// const toggleAll = () => {
//   const checked = states.value.every((s) => s.checked)
//   states.value.forEach((s) => (s.checked = !checked))
// }
</script>

<style lang="scss" scoped>
.timeframe-menu {
  height: auto;
}

.checkbox {
  align-items: center;
  display: flex;
  margin-left: 0 !important;
  width: min-content;

  ::v-deep(input) {
    -moz-appearance: inherit;
  }
}
</style>
