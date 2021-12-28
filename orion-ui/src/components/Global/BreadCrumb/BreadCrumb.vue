<template>
  <component
    v-skeleton="!crumb.text"
    :is="crumb.to ? 'router-link' : 'span'"
    :to="crumb.to"
    class="text-truncate"
  >
    {{ crumb.text }}
  </component>
</template>

<script lang="ts" setup>
type Crumb = {
  text: string
  to?: string
}

defineProps<{ crumb: Crumb }>()
</script>

<style lang="scss" scoped>
a {
  text-decoration: none;

  &:hover {
    color: $primary !important;
    text-decoration: underline;
  }

  &:active {
    color: $primary-hover !important;
  }
}
</style>
