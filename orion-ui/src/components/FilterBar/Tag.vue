<template>
  <button class="tag font--secondary caption" tabindex="0" role="button">
    <div class="px-1 py--half d-flex align-center">
      <slot />

      <i
        v-if="props.clearable"
        class="pi pi-xs pi-close-circle-fill ml-1"
        role="button"
        title="Clear"
        @click="emit('remove')"
      />
    </div>
  </button>
</template>

<script lang="ts" setup>
import { defineEmits, defineProps } from 'vue'

const props = defineProps<{ clearable?: boolean }>()
const emit = defineEmits(['remove'])
</script>

<style lang="scss" scoped>
@use '@/styles/components/global-filter--tag.scss';
</style>
