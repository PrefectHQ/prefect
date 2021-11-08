<template>
  <div class="wrapper">
    <div class="pulse" />

    <div
      class="
        overflow-node
        text--white text--secondary
        d-flex
        align-center
        justify-center
      "
    >
      +
      {{ props.nodes?.size && props.nodes?.size > 99 ? 99 : props.nodes?.size }}
      {{ props.nodes?.size && props.nodes?.size > 99 ? '+' : '' }}
    </div>
  </div>
</template>

<script lang="ts" setup>
import { defineProps } from 'vue'
import { SchematicNodes } from '@/typings/schematic'

const props = defineProps<{
  nodes?: SchematicNodes
}>()
</script>

<style lang="scss">
.wrapper {
  transition: top 150ms, left 150ms, transform 150ms, box-shadow 50ms;
  transform: translate(-50%, -50%);

  .overflow-node {
    background-color: #0a2053;
    border-radius: 50%;
    box-shadow: 0px 0px 6px rgb(8, 29, 65, 0.06);
    box-sizing: content-box;
    // These don't work in firefox yet but are being prototyped (https://github.com/mozilla/standards-positions/issues/135)
    cursor: pointer;
    height: 53px;
    pointer-events: all;

    width: 53px;

    &:hover {
      box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.06),
        0px 1px 3px rgba(0, 0, 0, 0.1);
    }
  }

  .pulse {
    animation: 5s ease-in-out infinite pulse;
    background-color: rgba(0, 0, 0, 0.1);
    border-radius: 50%;
    height: 100%;
    width: 100%;
    position: absolute;
    transform-origin: center;
    z-index: -1;
  }
}

@keyframes pulse {
  0% {
    transform: scale(1);
  }

  20% {
    transform: scale(1.25);
  }

  30% {
    transform: scale(1);
  }

  100% {
    transform: scale(1);
  }
}
</style>
