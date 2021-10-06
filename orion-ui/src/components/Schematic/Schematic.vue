<template>
  <div class="schematic-container" ref="container" @scroll="preventScroll">
    <svg ref="svg" class="schematic-svg">
      <defs id="defs" />
      <g id="edge-container" />
      <g id="ring-container" />
    </svg>

    <div class="node-container">
      <Node
        v-for="[key, node] of visibleNodes"
        :id="`node-${key}`"
        :key="key"
        :node="node"
        :collapsed="collapsedTrees.get(key) ? true : false"
        :style="{ left: node.cx + 'px', top: node.cy + 'px' }"
        tabindex="0"
        @toggle-tree="toggleTree"
        @focus.self="panToNode(node)"
      />
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, defineProps, computed, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'
import { RadialSchematic } from './util'
import { curveMetro } from './curveMetro'

import Node from './Node.vue'

import {
  Item,
  Link,
  SchematicNodes,
  SchematicNode,
  Rings,
  Ring,
  Links
} from '@/typings/schematic'

const props = defineProps<{ items: Item[] }>()
const items = ref<Item[]>(props.items)

/**
 * Selection Refs
 */
type Selection = d3.Selection<SVGGElement, unknown, HTMLElement, any>

const container = ref<HTMLElement>()
const svg = ref<Selection>()
const defs = ref<Selection>()
const edgeContainer = ref<Selection>()
const ringContainer = ref<Selection>()
const nodeContainer = ref<Selection>()

/**
 * Computed
 */
const scaleExtentLower = computed<number>(() => {
  return (
    (1 / (radial.value.rings.size * baseRadius * 3)) *
    Math.max(height.value, width.value)
  )
})

const visibleNodes = computed<SchematicNodes>(() => {
  const collapsed = [...collapsedTrees.entries()]
  return new Map(
    [...radial.value.nodes.entries()].filter(([, node]) =>
      collapsed.every(([, tree]) => !tree.get(node.id))
    )
  )
})

const visibleRings = computed<Rings>(() => {
  const rings = new Set(
    [...visibleNodes.value.entries()].map(([, node]) => node.ring)
  )
  return new Map(
    [...radial.value.rings.entries()].filter(([key]) => rings.has(key))
  )
})

const visibleLinks = computed<Links>(() => {
  const collapsed = [...collapsedTrees.entries()]
  return radial.value.links.filter((link: Link) =>
    collapsed.every(([, tree]) => !tree.get(link.target.id))
  )
})

/**
 * Methods
 */
const zoomed = ({
  transform
}: {
  transform: { x: number; y: number; k: number }
}): void => {
  console.log('zoomed', transform)
  const ts = `translate(${transform.x}px, ${transform.y}px) scale(${transform.k})`
  ringContainer.value?.style('transform', ts)
  edgeContainer.value?.style('transform', ts)
  nodeContainer.value?.style('transform', ts)
}

const toggleTree = (node: SchematicNode) => {
  if (collapsedTrees.get(node.id)) {
    collapsedTrees.delete(node.id)
  } else {
    const tree = radial.value.traverse(node)
    collapsedTrees.set(node.id, tree)
  }
}

const updateCanvas = (): void => {
  ringContainer.value
    ?.selectAll('.ring')
    .data(visibleRings.value)
    .join(
      // enter
      (selection: any) => {
        const g = selection.append('g')
        g.attr('id', (d: any) => d.id)
        const circle = g.attr('class', 'ring').append('circle')
        circle
          .attr('cx', width.value / 2)
          .attr('cy', height.value / 2)
          .attr('id', ([key]: [number, Ring]) => key)
          .attr('r', ([, d]: [number, Ring]) => d.radius)
          .style('opacity', 1)
          .attr('fill', 'transparent')
          .attr('stroke', 'rgba(0, 0, 0, 0.02)')
          .attr('stroke-width', '50px')
        return g
      },
      // update
      (selection: any) => {
        const circle = selection.select('circle')
        circle
          .attr('cx', width.value / 2)
          .attr('cy', height.value / 2)
          .attr('id', ([key]: [number, Ring]) => key)
          .attr('r', ([, d]: [number, Ring]) => d.radius)
        return selection
      },
      // exit
      (selection: any) => selection.remove()
    )
  // TODO: Edges that traverse rings should be _much_ fainter
  // than edges with dependencies on the previous ring
  const calcGradientCoord = (d: Link) => {
    const x1 = d.source.cx
    const y1 = d.source.cy
    const x2 = d.target.cx
    const y2 = d.target.cy
    return {
      x1: x1,
      x2: x2,
      y1: y1,
      y2: y2
    }
  }
  const animated = (state: string) => ['pending', 'running'].includes(state)
  if (useLinearGradient) {
    // An alternative to using defs is to only use the edges
    // but add an animated portion to the actual element
    // ... that will likely be more performant
    defs.value
      ?.selectAll('linearGradient')
      .data(visibleLinks.value)
      .join(
        // enter
        (selection: any) => {
          const g = selection.append('linearGradient')
          g.attr('id', (d: Link, i: number) => d.source.data.name + i)
            .attr(
              'class',
              (d: Link) => `${d.source.data.state.type.toLowerCase()}-text`
            )
            .attr('gradientUnits', 'userSpaceOnUse')
            .attr('x1', (d: Link) => calcGradientCoord(d).x1)
            .attr('y1', (d: Link) => calcGradientCoord(d).y1)
            .attr('x2', (d: Link) => calcGradientCoord(d).x2)
            .attr('y2', (d: Link) => calcGradientCoord(d).y2)
          g.append('stop').attr('offset', '0%').attr('stop-opacity', 1)
          const animatedStop = g.append('stop')
          animatedStop.attr('offset', '25%').attr('stop-opacity', 0.05)
          animatedStop
            .append('animate')
            .attr('attributeName', 'offset')
            .attr('values', (d: Link) =>
              animated(d.source.data.state) ? '25%; 75%; 25%;' : '25%; 75%;'
            )
            .attr('fill', 'freeze')
            .attr('dur', (d: Link) =>
              animated(d.source.data.state) ? '5s' : '2s'
            )
            .attr('repeatCount', (d: Link) =>
              animated(d.source.data.state) ? 'indefinite' : 1
            )
          return g
        },
        // update
        (selection: any) => {
          selection
            .attr('id', (d: Link, i: number) => d.source.data.name + i)
            .attr(
              'class',
              (d: Link) => `${d.source.data.state.type.toLowerCase()}-text`
            )
            .attr('gradientUnits', 'userSpaceOnUse')
            .attr('x1', (d: Link) => calcGradientCoord(d).x1)
            .attr('y1', (d: Link) => calcGradientCoord(d).y1)
            .attr('x2', (d: Link) => calcGradientCoord(d).x2)
            .attr('y2', (d: Link) => calcGradientCoord(d).y2)
          selection
            .select('animate')
            .attr('values', (d: Link) =>
              animated(d.source.data.state) ? '25%; 75%; 25%;' : '25%; 75%;'
            )
            .attr('dur', (d: Link) =>
              animated(d.source.data.state) ? '5s' : '2s'
            )
            .attr('repeatCount', (d: Link) =>
              animated(d.source.data.state) ? 'indefinite' : 1
            )
          return selection
        },
        // exit
        (selection: any) => selection.remove()
      )
  }

  edgeContainer.value
    ?.selectAll('path')
    .data(visibleLinks.value)
    .join(
      // enter
      (selection: any) =>
        selection
          .append('path')
          .attr('id', (d: Link) => d.source.id + '-' + d.target.id)
          .attr(
            'class',
            (d: Link) => `${d.source.data.state.type.toLowerCase()}-stroke`
          )
          .style('stroke', (d: Link, i: number) =>
            useLinearGradient ? `url("#${d.source.data.name + i}")` : null
          )
          .style('stroke-width', (d: Link) =>
            d.source.data.state == 'pending' ? 5 : 20
          )
          .attr('d', (d: Link) =>
            line([
              [d.source.cx, d.source.cy],
              [d.target.cx, d.target.cy]
            ])
          )
          .style('opacity', 1),
      // update
      (selection: any) =>
        selection
          .attr('id', (d: Link) => d.source.id + '-' + d.target.id)
          .attr(
            'class',
            (d: Link) => `${d.source.data.state.type.toLowerCase()}-stroke`
          )
          .style('stroke', (d: Link, i: number) =>
            useLinearGradient ? `url("#${d.source.data.name + i}")` : null
          )
          .style('stroke-width', (d: Link) =>
            d.source.data.state == 'pending' ? 5 : 20
          )
          .attr('d', (d: Link) =>
            line([
              [d.source.cx, d.source.cy],
              [d.target.cx, d.target.cy]
            ])
          )
          .style('opacity', 1),
      // exit
      (selection: any) => selection.remove()
    )
}

const panToNode = (item: Item | SchematicNode): void => {
  const node = visibleNodes.value.get(item.id)
  if (!node) return
  ;(document.querySelector(`#node-${item.id}`) as HTMLElement)?.focus()

  const zoomIdentity = d3.zoomIdentity
    .translate(width.value / 2, height.value / 2)
    .scale(1)
    .translate(-node.cx, -node.cy)

  d3.select('.schematic-svg')
    .transition()
    .duration(250)
    .call(zoom.value.transform, zoomIdentity)
}

/**
 * Schematic refs
 */
const useLinearGradient: boolean = false
const height = ref<number>(0)
const width = ref<number>(0)
const baseRadius: number = 300

const collapsedTrees: Map<string, Map<string, SchematicNode>> = new Map()
const radial = ref<RadialSchematic>(new RadialSchematic())
const line = d3.line().curve(curveMetro)

const zoom = ref<d3.ZoomBehavior<any, any>>(d3.zoom())

/**
 * Watchers
 */
watch(props, () => {
  items.value = props.items
  radial.value.center([width.value / 2, height.value / 2]).items(items.value)
  requestAnimationFrame(() => updateCanvas())
})

watch(visibleRings, () => {
  zoom.value.scaleExtent([scaleExtentLower.value, 1])
})

watch(visibleLinks, () => {
  requestAnimationFrame(() => updateCanvas())
})

/**
 * Init
 */
const handleWindowResize = (): void => {
  if (!container.value) return
  height.value = container.value.offsetHeight
  width.value = container.value.offsetWidth
}

const createChart = (): void => {
  svg.value = d3.select('.schematic-svg')
  defs.value = d3.select('#defs')
  ringContainer.value = svg.value.select('#ring-container')
  edgeContainer.value = svg.value.select('#edge-container')
  nodeContainer.value = d3.select('.node-container')
  ringContainer.value.attr('class', 'ring-container')
  edgeContainer.value.attr('class', 'edge-container')

  zoom.value = d3
    .zoom()
    .extent([
      [0, 0],
      [width.value, height.value]
    ])
    .scaleExtent([scaleExtentLower.value, 1])
    // .filter((e: Event) => e?.type !== 'wheel' && e?.type !== 'dblclick') // Disables user mouse wheel and double click zoom in/out
    .on('zoom', zoomed)

  svg.value
    ?.attr('viewbox', `0, 0, ${width.value}, ${height.value}`)
    .call(zoom.value)

  updateCanvas()
}

// This is used to prevent scrolling of the container when
// an out of view node is focused... we handle that with a transform event
// to maintain state with the d3 elements
const preventScroll = (e: Event) => {
  e.preventDefault()
  if (!container.value) return
  container.value.scrollTop = 0
  container.value.scrollLeft = 0
}

onMounted(() => {
  handleWindowResize()
  window.addEventListener('resize', handleWindowResize)

  radial.value
    .id('id')
    .dependencies('upstream_dependencies')
    .center([width.value / 2, height.value / 2])
    .items(items.value)

  createChart()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleWindowResize)
})
</script>

<style scoped lang="scss">
.schematic-container {
  height: 100vh;
  max-height: 100vh;
  max-width: 100%;
  overflow: hidden;
  position: fixed;
  width: 100%;

  svg,
  canvas {
    cursor: grab;
    height: inherit;
    left: 0;
    position: absolute;
    overflow: hidden;
    top: 0;
    width: inherit;

    &:active {
      cursor: grabbing;
    }
  }
}

.node-container {
  pointer-events: none;
  position: absolute;
  user-select: none;
  transform-origin: 0 0;
  top: 0;
  left: 0;
  z-index: 0;
}
</style>

<style lang="scss">
.schematic-container {
  svg {
    path {
      // display: none;
      fill: none;
      opacity: 0.8;
      stroke-width: 20;
      stroke-opacity: 0.4;
      stroke-linejoin: round;

      &.success {
        color: var(--completed) !important;
        stroke: currentColor;
      }

      &.failed {
        color: var(--failed) !important;
        stroke: currentColor;
      }

      &.pending {
        color: var(--pending);
        stroke: currentColor;
        stroke-width: 5;
        stroke-dasharray: 4;
      }
    }
  }

  linearGradient {
    &.success {
      color: var(--completed) !important;
    }

    &.failed {
      color: var(--failed) !important;
    }

    &.pending {
      color: var(--pending);
    }
  }

  stop {
    stop-color: currentColor;
  }
}
</style>
