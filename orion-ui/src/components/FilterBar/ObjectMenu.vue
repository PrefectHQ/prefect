<template>
  <Card class="menu font--primary" miter shadow="sm" tabindex="0">
    <button
      v-for="option in options"
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
import { computed, defineEmits } from 'vue'
import { useStore } from 'vuex'

const store = useStore()

const emit = defineEmits(['close'])

type option = { label: string; value: string }
const options: option[] = [
  { label: 'Flows', value: 'flows' },
  { label: 'Deployments', value: 'deployments' },
  { label: 'Flow Runs', value: 'flow_runs' },
  { label: 'Task Runs', value: 'task_runs' }
]

const value = computed(() => {
  return store.getters.globalFilter.object
})

const selectOption = (val: string) => {
  emit('close')
  store.commit('object', val)
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
