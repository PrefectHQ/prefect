<template>
  <div class="container">
    <div class="font-weight-semibold d-flex align-center">
      <i class="pi text--grey-40 mr-1 pi-sm" :class="icon" />
      {{ title }}
    </div>

    <a
      class="font--secondary text--primary text-decoration-none my-1 d-block"
      @click="toggleAll"
    >
      Select All
    </a>

    <m-checkbox
      v-for="state in availableStates"
      :key="state.type"
      :modelValue="!!states.find((s) => s.type == state.type)"
      class="d-flex my-1 font--secondary checkbox text-left"
      @change="toggleState(state)"
    >
      <span>{{ state.name }}</span>
    </m-checkbox>
  </div>
</template>

<script lang="ts" setup>
import { ref, watch, withDefaults } from 'vue'

const emit = defineEmits(['close', 'update:modelValue'])

const props = withDefaults(
  defineProps<{
    modelValue?: { name: string; type: string }[]
    title?: string
    icon?: string
  }>(),
  { modelValue: () => [], title: 'States', icon: 'pi-history-fill' }
)

const states = ref([...props.modelValue])

const availableStates = [
  { name: 'Scheduled', type: 'SCHEDULED' },
  { name: 'Pending', type: 'PENDING' },
  { name: 'Running', type: 'RUNNING' },
  { name: 'Completed', type: 'COMPLETED' },
  { name: 'Failed', type: 'FAILED' },
  { name: 'Cancelled', type: 'CANCELLED' }
]

const toggleState = (state: { name: string; type: string }) => {
  const index = states.value.findIndex((s) => s.type == state.type)

  if (index > -1) {
    states.value.splice(index, 1)
  } else {
    states.value.push(state)
  }
}

const toggleAll = () => {
  // There might be a better way to do this while maintaining reactivity
  if (states.value.length == availableStates.length) {
    states.value.length = 0
  } else {
    states.value.length = 0
    availableStates.forEach((s) => toggleState(s))
  }
}

watch(states.value, () => {
  emit('update:modelValue', states.value)
})
</script>

<style lang="scss" scoped>
.container {
  width: 100%;
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
