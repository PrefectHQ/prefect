<template>
  <button type="button" class="button-card">
    <m-card v-bind="{ width, height, shadow, miter }" class="button-card__card">
      <div class="button-card__content">
        <slot />
      </div>
    </m-card>
  </button>
</template>

<script lang="ts" setup>
  import { withDefaults } from 'vue'

  withDefaults(defineProps<{
    height?: string,
    width?: string,
    shadow?: string | null,
    miter?: boolean,
  }>(), {
    height: 'inherit',
    width: 'inherit',
    shadow: null,
  })
</script>

<style lang="scss">
.button-card {
  cursor: pointer;
}

.button-card__content {
  padding: var(--p-1);
}
 </style>