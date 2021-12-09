<template>
  <div
    ref="container"
    class="mini-radar position-relative"
    :class="{ 'mini-radar--disabled': props.disableInteractions }"
    @mousemove="dragViewport"
    @mouseleave="dragging = false"
  >
    <svg class="mini-radar__canvas" @click="pan">
      <g class="mini-radar__ring-container" />
    </svg>

    <div
      v-if="!hideViewport"
      ref="viewport"
      class="mini-radar__viewport position-absolute"
      :style="viewportStyle"
      @mousedown="dragging = true"
      @mouseup="dragging = false"
    />
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted, watch, withDefaults } from 'vue'
import * as d3 from 'd3'
import { Radar } from './Radar'
import { generateArcs, calculateArcSegment, Arc } from './utils'

import { RadarNodes, RadarNode, Rings, Ring } from '@/typings/radar'

const emit = defineEmits(['drag-viewport', 'pan-to-location'])

const props = withDefaults(
  defineProps<{
    radar: Radar
    collapsedTrees?: Map<string, Map<string, RadarNode>>
    transform?: { x: number; y: number; k: number }
    height?: number
    width?: number
    id: string
    baseRadius?: number
    disableInteractions?: boolean
    hideViewport?: boolean
  }>(),
  {
    baseRadius: 300,
    hideViewport: false,
    disableInteractions: false,
    transform: () => {
      return { x: 0, y: 0, k: 1 }
    }
  }
)

/**
 * Selection Refs
 */
type Selection = d3.Selection<SVGGElement, unknown, HTMLElement, any>

const container = ref<HTMLElement>()
const viewport = ref<HTMLElement>()
const canvas = ref<Selection>()
const ringContainer = ref<Selection>()

/**
 * Misc refs
 */
const dragging = ref<boolean>(false)

/**
 * Computed
 */
const visibleNodes = computed<RadarNodes>(() => {
  const collapsed = [
    ...(props.collapsedTrees?.entries() || new Map().entries())
  ]
  return new Map(
    [...props.radar.nodes.entries()]
      .filter(([, node]) => collapsed.every(([, tree]) => !tree.get(node.id)))
      .filter(([, node]) => {
        // This is currently filtering out nodes that share a single position (showing only the first one that got the spot)
        const ring: Ring | undefined = props.radar.rings.get(node.ring)
        if (!ring) return
        const position = node.position
        if (!position) return
        const positionalArr = [...position.nodes.values()]
        return positionalArr?.[0]?.id == node.id
      })
  )
})

const visibleRings = computed<Rings>(() => {
  const rings = new Set(
    [...visibleNodes.value.entries()].map(([, node]) => node.ring)
  )
  return new Map(
    [...props.radar.rings.entries()].filter(([key]) => rings.has(key))
  )
})

const viewportOffset = computed<number>(() => {
  const radii = [...visibleRings.value.entries()].map(([, ring]) => ring.radius)
  return Math.max(...radii, props.baseRadius * 2)
})

const scale = computed<number>(() => {
  const scale_ = 200 / (viewportOffset.value * 2.5)
  return scale_
})

const viewportStyle = computed<{
  width: string
  height: string
}>(() => {
  return {
    height: dimensions.value.height + 'px',
    width: dimensions.value.width + 'px'
  }
})

const dimensions = computed<{ width: number; height: number }>(() => {
  if (!props.height || !props.width) return { height: 0, width: 0 }
  return {
    height: props.height * scale.value,
    width: props.width * scale.value
  }
})

/**
 * Methods
 */
const updateRings = (): void => {
  const classGenerator = (d: Arc): string => {
    const strokeClass = d.state ? `${d.state}-stroke` : ''
    return `radar__arc-segment ${strokeClass}`
  }

  ringContainer.value
    ?.style('transform', `scale(${scale.value})`)
    .selectAll('.radar__arc-segment-group')
    .data(visibleRings.value)
    .join(
      // enter
      (selection: any) =>
        selection.append('g').attr('class', 'radar__arc-segment-group'),
      // update
      (selection: any) => selection,
      // exit
      (selection: any) => selection.remove()
    )
    .selectAll('.radar__arc-segment')
    .data((d: [number, Ring]) => generateArcs(d, props.baseRadius))
    .join(
      // enter
      (selection: any) =>
        selection
          .append('path')
          .attr('class', classGenerator)
          .attr('fill', 'transparent')
          .attr('stroke', 'rgba(0, 0, 0, 0.1)')
          .attr('stroke-width', 80)
          .attr('d', (d: Arc) => calculateArcSegment(d)),
      (selection: any) =>
        selection
          .attr('class', classGenerator)
          .attr('d', (d: Arc) => calculateArcSegment(d)),
      // exit
      (selection: any) => selection.remove()
    )
}

const dragViewport = (e: MouseEvent): void => {
  if (!dragging.value || props.disableInteractions) return

  // We multiply the mouse movement by a multiplier equal to the inverse
  // of the scale applied to the minimap
  const x = e.movementX * -(1 / scale.value)
  const y = e.movementY * -(1 / scale.value)
  emit('drag-viewport', { x: x, y: y })
}

const pan = (e: MouseEvent): void => {
  if (props.disableInteractions) return
  const rect = (e.target as Element)?.getBoundingClientRect()

  const x_ = (e.clientX - rect.left - 100) / scale.value
  const y_ = (e.clientY - rect.top - 100) / scale.value
  const zoomIdentity = d3.zoomIdentity
    .scale(props.transform.k)
    .translate(-x_, -y_)

  emit('pan-to-location', zoomIdentity)
}

/**
 * Watchers
 */
watch(
  () => props.transform,
  () => {
    if (viewport.value) {
      const x =
        (1 - props.transform.x / props.transform.k) * scale.value +
        100 -
        dimensions.value.width / 2
      const y =
        (1 - props.transform.y / props.transform.k) * scale.value +
        100 -
        dimensions.value.height / 2

      viewport.value.style.transform = `translate(${x}px, ${y}px) scale(${
        1 / props.transform.k
      })`
      viewport.value.style.borderRadius = `${Math.max(
        4 * props.transform.k,
        4
      )}px`
    }
  }
)

watch(visibleRings, () => requestAnimationFrame(() => updateRings()))

/**
 * Init
 */
const createChart = (): void => {
  canvas.value = d3.select('.mini-radar__canvas')
  ringContainer.value = canvas.value.select('.mini-radar__ring-container')
  ringContainer.value.style('transform', `scale(${scale.value})`)

  if (container.value) {
    canvas.value
      ?.attr(
        'viewbox',
        `0, 0, ${container.value.offsetWidth}, ${container.value.offsetHeight}`
      )
      .attr('width', container.value.offsetWidth)
      .attr('height', container.value.offsetHeight)
  }

  updateRings()
}

onMounted(() => {
  createChart()
})
</script>

<style lang="scss" scoped>
@use '@prefecthq/miter-design/src/styles/abstracts/variables' as *;

.mini-radar {
  $self: &;

  height: 100%;
  overflow: hidden;
  width: 100%;

  &__canvas {
    cursor: pointer;
    height: inherit;
    left: 0;
    overflow: hidden;
    top: 0;
    width: inherit;

    &:active {
      cursor: grabbing;
    }
  }

  &__viewport {
    background-color: rgba(63, 150, 216, 0.2);
    border-radius: 8px;
    cursor: grab;
    left: 0;
    top: 0;
    transform-origin: top left;
    z-index: 2;

    &:active {
      cursor: grabbing;
    }
  }

  &--disabled {
    cursor: default !important;

    #{$self}__canvas {
      cursor: default !important;
    }

    #{$self}__viewport {
      cursor: default !important;

      &:active {
        cursor: default;
      }
    }
  }
}
</style>

<style lang="scss">
.mini-radar {
  &__arc-segment-group {
    pointer-events: none;
  }

  &__ring-container {
    transform-origin: center;
  }
}
</style>
