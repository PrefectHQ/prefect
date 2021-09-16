<template>
  <div class="row" :class="{ 'hide-scrollbars': hideScrollbars }">
    <slot />
  </div>
</template>

<script lang="ts">
import { Vue, prop, Options } from 'vue-class-component'

class Props {
  hideScrollbars = prop<Boolean>({
    required: false,
    default: false,
    type: Boolean
  })
}

@Options({})
export default class Row extends Vue.with(Props) {}
</script>

<style lang="scss" scoped>
.row {
  overflow: auto;
  white-space: nowrap;

  // These are based on application-wide margins/padding; we might want to componentize these at some point
  margin-left: -32px;
  padding-left: 32px;
  padding-right: 32px;
  width: calc(100% + 64px);

  &.hide-scrollbars {
    scrollbar-width: none; // Edge
    -ms-overflow-style: none; // Firefox

    // Chrome, Safari
    ::-webkit-scrollbar {
      display: none;
    }
  }
}

@media (max-width: 640px) {
  .row {
    margin-left: -16px;
    padding-left: 16px;
    padding-right: 16px;
    width: calc(100% + 32px);
  }
}
</style>
