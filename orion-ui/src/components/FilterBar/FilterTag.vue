<template>
  <button class="filter-tag font--secondary caption" tabindex="0" role="button">
    <div class="px-1 py--half d-flex align-center">
      <i v-if="item.icon" class="pi pi-xs mr--half" :class="item.icon" />
      {{ item.label }}

      <i
        v-if="item.clearable"
        class="pi pi-xs pi-close-circle-fill ml-1"
        role="button"
        title="Clear filter"
        @click="emit('remove', props.item)"
      />
    </div>
  </button>
</template>

<script lang="ts" setup>
import { defineEmits, defineProps } from 'vue'

const props =
  defineProps<{ item: { label: string; icon: string; clearable: boolean } }>()
const emit = defineEmits(['remove'])
</script>

<style lang="scss" scoped>
@use '@/styles/components/global-filter--filter-tag.scss';
</style>
