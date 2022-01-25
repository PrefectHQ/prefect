<template>
  <component
    v-skeleton="!crumb.text"
    :is="crumb.to ? 'router-link' : 'span'"
    :to="crumb.to"
    class="text-truncate bread-crumb"
    :style="{
      minWidth: !crumb.text ? '40px' : undefined,
      maxWidth: '50%',
      minHeight: '30px'
    }"
  >
    {{ crumb.text }}
  </component>
</template>

<script lang="ts" setup>
import { Crumb } from '../utils'

defineProps<{ crumb: Crumb }>()
</script>

<style lang="scss" scoped>
a {
  text-decoration: none;

  &:hover {
    color: $primary;
    text-decoration: underline;
  }

  &:active {
    color: $primary-hover !important;
  }
}

.bread-crumb::after {
  content: '\00a0/\00a0';
}

.bread-crumb:last-child::after {
  display: none;
}
</style>
