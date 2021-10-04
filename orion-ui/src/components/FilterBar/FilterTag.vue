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
@use '@/styles/components/global-filter--filter-tag.scss';
</style>
