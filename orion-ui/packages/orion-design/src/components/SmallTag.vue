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
  height: auto !important;
  padding: 2px 4px !important;
  font-family: barlow;
  font-weight: 600;
  font-size: 13px;
  line-height: 13px;
}
</style>