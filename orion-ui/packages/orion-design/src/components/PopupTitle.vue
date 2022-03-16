<template>
  <h3 class="font-weight-semibold d-flex align-center" :class="[`text--${color ?? 'primary'}`]">
    <slot>
      <i class="pi" :class="icon" />
      <span class="ml-1">{{ title }}</span>
    </slot>
  </h3>
</template>

<script lang="ts" setup>
  interface IPopupTitleProps {
    color?: string,
    icon?: string,
    title?: string,
  }

  defineProps<IPopupTitleProps>()
</script>