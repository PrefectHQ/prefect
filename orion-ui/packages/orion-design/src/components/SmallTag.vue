<template>
  <m-tag class="small-tag" v-bind="$attrs">
    <slot />
  </m-tag>
</template>

<script lang="ts">
  import { defineComponent } from 'vue'

  export default defineComponent({
    name: 'FilterBar',
    expose: [],
    inheritAttrs: false,
  })
</script>

<style lang="scss">
.small-tag > span {
  padding: 0 var(--p-1) !important;
  font-size: 13px;
}
</style>