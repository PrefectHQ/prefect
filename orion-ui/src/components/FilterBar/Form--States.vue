<template>
  <div>
    <div class="font-weight-semibold">Run States</div>

    <a
      class="font--secondary text--primary text-decoration-none my-1 d-block"
      @click="toggleAll"
    >
      Select All
    </a>

    <Checkbox
      v-for="state in availableStates"
      :key="state"
      :modelValue="!!states.find((s) => s.type == state.type)"
      class="d-flex my-1 font--secondary checkbox text-left"
      @change="toggleState(state)"
    >
      <span>{{ state.name }}</span>
    </Checkbox>
  </div>
</template>

<script lang="ts" setup>
import { defineEmits, ref, defineProps, watch } from 'vue'

const emit = defineEmits(['close', 'update:modelValue'])

const props = defineProps<{ modelValue: { name: string; type: string }[] }>()
console.log(props.modelValue)
const states = ref(props.modelValue)

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
  if (states.value.length == availableStates.length) {
    states.value = []
  } else {
    states.value = availableStates
  }
}
</script>

<style lang="scss" scoped>
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
