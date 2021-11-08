<template>
  <div class="overflow-node text--secondary d-flex align-center justify-center">
    <i class="pi pi-more-fill pi-lg" />
  </div>
</template>

<script lang="ts" setup>
import { defineProps } from 'vue'

const props = defineProps({})
</script>

<style lang="scss">
.overflow-node {
  //   visibility: hidden;
  background-color: white;
  border-radius: 50%;
  box-shadow: 0px 0px 6px rgb(8, 29, 65, 0.06);
  box-sizing: content-box;
  // These don't work in firefox yet but are being prototyped (https://github.com/mozilla/standards-positions/issues/135)
  contain-intrinsic-size: 300px 60px;
  content-visibility: hidden;
  overflow: visible;
  cursor: pointer;
  height: 53px;
  pointer-events: all;
  transition: top 150ms, left 150ms, transform 150ms, box-shadow 50ms;
  transform: translate(-50%, -50%);
  width: 53px;

  &.observed {
    visibility: visible;
    content-visibility: visible;
  }

  &:hover {
    box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.06), 0px 1px 3px rgba(0, 0, 0, 0.1);
  }

  &:focus {
    border-width: 2px;
    border-style: solid;
    transition: border-color 150ms;
    outline: none;
  }

  .border {
    border-top-left-radius: 8px;
    border-bottom-left-radius: 8px;
    height: 100%;
  }

  .collapse-link {
    &:hover {
      background-color: var(--grey-5);
    }

    > i {
      color: rgba(0, 0, 0, 0.3);
    }
  }
}
</style>
