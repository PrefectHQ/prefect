<template>
  <component
    :is="crumb.to ? 'router-link' : 'span'"
    v-skeleton="!crumb.text"
    :to="crumb.to"
    class="text-truncate bread-crumb"
    :style="{ minWidth: !crumb.text ? '40px' : undefined }"
  >
    {{ crumb.text }}
  </component>
</template>

<script lang="ts" setup>
  import { Crumb } from '@/models/Crumb'

  defineProps<{ crumb: Crumb }>()
</script>

<style lang="scss" scoped>
a {
  text-decoration: none;

  &:hover {
    color: var(--primary);
    text-decoration: underline;
  }

  &:active {
    color: var(--primary-hover) !important;
  }
}

.bread-crumb {
  max-width: 50%;
  min-height: 30px;
}

.bread-crumb::after {
  content: '\00a0/\00a0';
}

.bread-crumb:last-child::after {
  display: none;
}
</style>
