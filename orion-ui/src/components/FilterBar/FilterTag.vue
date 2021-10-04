<template>
  <div class="filter-tag mr-1 font--secondary caption" tabindex="0">
    <div class="px-1 py--half d-flex align-center text-capitalize">
      <i class="pi pi-xs mr--half" :class="item.icon" />
      {{ item.objectLabel }}

      <i
        class="pi pi-xs pi-close-circle-fill ml-1"
        role="button"
        title="Clear filter"
        @click="emit('remove', props.item)"
      />
    </div>
  </div>
</template>

<script lang="ts" setup>
import { defineEmits, defineProps } from 'vue'
import { FilterObject } from './util'

const props = defineProps<{ item: FilterObject }>()
const emit = defineEmits(['remove'])
</script>

<style lang="scss" scoped>
@use '@prefecthq/miter-design/src/styles/abstracts/variables' as *;
@use '@prefecthq/miter-design/src/styles/abstracts/mixins' as mixins;

.filter-tag {
  @include mixins.miter(1, 1);

  > div {
    background-color: $blue-20;
    border-radius: 4px;
    color: $grey-80;
    cursor: pointer;

    &:hover,
    &:focus {
      background-color: $blue-40;
    }
  }

  i {
    border-radius: 50%;
    border: none;
    color: $primary;
    cursor: pointer;
    outline: none;
    padding: 0;
    width: min-content;

    &:hover,
    &:focus {
      color: $primary-hover;
    }

    &:active {
      color: $primary-pressed;
    }
  }
}
</style>
