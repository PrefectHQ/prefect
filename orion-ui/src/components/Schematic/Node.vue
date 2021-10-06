<template>
  <div class="node">
    <!-- :class="[
        node.data.state.toLowerCase() + '-bg',
        node.data.state.toLowerCase() + '-border'
      ]"
    :class="node.data.state.toLowerCase() + '-border'" -->
    <!-- <div class="d-flex align-center justify-center border px-1">

      <i
        class="pi text--white pi-lg"
        :class="'pi-' + state.type.toLowerCase()"
      />
    </div> -->

    <div class="d-flex align-center justify-center px-1">
      <div class="text-truncate" style="width: 110px">
        <!-- {{ node.data.name }} - {{ node.ring }} -->
      </div>

      <a
        v-if="node.downstreamNodes.size > 0"
        class="collapse-link"
        tabindex="-1"
        @click.stop="toggle"
      >
        {{ collapsed ? 'Show' : 'Hide' }}
      </a>

      <!-- <div class="text-caption-2">
              <span class="text--grey-4">D: </span>
              {{ node.downstreamNodes.size }}
              <span class="text--grey-4 ml-1">U: </span>
              {{ node.upstreamNodes.size }}
              <span class="text--grey-4 ml-1">P: </span>
              {{ node.position }}
            </div> -->
    </div>
  </div>
</template>

<script lang="ts" setup>
import { defineProps, computed, defineEmits } from 'vue'
import { SchematicNode } from '@/typings/schematic'
import { State } from '@/typings/objects'

const emit = defineEmits(['toggle-tree'])

const props = defineProps<{
  node: SchematicNode
  collapsed?: boolean
}>()

const toggle = () => {
  emit('toggle-tree', props.node)
}

const node = computed<SchematicNode>(() => {
  return props.node
})

const collapsed = computed(() => {
  return props.collapsed
})

const state = computed<State>(() => {
  return props.node.data.state
})
</script>

<style lang="scss" scoped>
.node {
  // visibility: hidden;
  background-color: white;
  border-radius: 10px;
  box-shadow: 0px 0px 6px rgb(8, 29, 65, 0.06);
  box-sizing: content-box;
  // These don't work in firefox yet but are being prototyped (https://github.com/mozilla/standards-positions/issues/135)
  contain-intrinsic-size: 53px;
  content-visibility: auto;
  cursor: pointer;
  position: absolute;
  //   height: 53px;
  height: 50px;
  pointer-events: all;
  transition: top 150ms, left 150ms, transform 150ms, box-shadow 50ms;
  transform: translate(-50%, -50%);
  //   width: 188px;
  width: 50px;

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
    border-top-left-radius: inherit;
    border-bottom-left-radius: inherit;
    margin-left: -2px;
    height: 100%;
  }

  .collapse-link {
    border-radius: 50%;
    // height: 20px;
    text-align: center;
    // width: 20px;

    &:hover {
      background-color: var(--grey-5);
    }

    > i {
      color: rgba(0, 0, 0, 0.3);
    }
  }
}
</style>
