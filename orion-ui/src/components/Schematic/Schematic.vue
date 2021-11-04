<template>
  <div class="schematic-container" ref="container" @scroll="preventScroll">
    <svg ref="svg" class="schematic-svg">
      <defs id="defs" />
      <g id="edge-container" />
      <g id="ring-container" />
    </svg>

    <!-- {{ positions }} -->

    <div class="node-container">
      <!-- <div v-for="[key, position] of radial?.positions" :key="key">
      {{
        position
      }}
      </div> -->

      <Node
        v-for="[key, node] of visibleNodes"
        :id="`node-${key}`"
        :key="key"
        :node="node"
        class="position-absolute"
        :collapsed="collapsedTrees.get(key)"
        :style="{ left: node.cx + 'px', top: node.cy + 'px' }"
        tabindex="0"
        @toggle-tree="toggleTree"
        @focus.self.stop="panToNode(node)"
        @click.self.stop="highlightNode(node)"
        @blur.self="highlightNode(node)"
      />

      <!-- <OverflowNode /> -->
      <!--  -->
    </div>

    <div class="mini-map position-absolute mr-2 mb-2" :style="miniMapStyle">
      <div
        ref="miniViewport"
        class="mini-map--viewport position-absolute"
        :style="miniMapViewportStyle"
      />
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, defineProps, computed, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'
import { RadialSchematic } from './util'
import { pow, sqrt } from './math'

import Node from './Node.vue'

import {
  Item,
  Link,
  SchematicNodes,
  SchematicNode,
  Rings,
  Ring,
  Links,
  Position,
  Positions
} from '@/typings/schematic'

const props = defineProps<{ items: Item[] }>()
const items = ref<Item[]>(props.items)

/**
 * Selection Refs
 */
type Selection = d3.Selection<SVGGElement, unknown, HTMLElement, any>

const container = ref<HTMLElement>()
const miniViewport = ref<HTMLElement>()
const svg = ref<Selection>()
const defs = ref<Selection>()
const edgeContainer = ref<Selection>()
const ringContainer = ref<Selection>()
const nodeContainer = ref<Selection>()

/**
 * Computed
 */
const visibleNodes = computed<SchematicNodes>(() => {
  const collapsed = [...collapsedTrees.value.entries()]
  return new Map(
    [...radial.value.nodes.entries()]
      .filter(([, node]) => collapsed.every(([, tree]) => !tree.get(node.id)))
      .filter(([, node]) => {
        // This is currently filtering out nodes that share a single position (showing only the first one that got the spot)
        const ring: Ring | undefined = radial.value.rings.get(node.ring)!
        const positions = ring.positions.get(node.position)!
        const positionalArr = [...positions.nodes.values()]
        return positionalArr?.[0]?.id == node.id
      })
  )
})

const positions = computed<Positions>(() => {
  return radial.value?.positions
  // if (!radial.value?.rings) return []
  // const rings: [number, Ring][] = [...radial.value.rings.entries()]
  // return rings.reduce((acc: Positions, [, ring]: [number, Ring]) => {
  //   acc.push.apply(acc, [...ring.positions.values()])
  //   // ring.positions.forEach((position: Position) => acc.push(position))
  //   return acc
  // }, [])
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
  const collapsed = [...collapsedTrees.value.entries()]
  return radial.value.links
    .filter((link: Link) =>
      collapsed.every(([, tree]) => !tree.get(link.target.id))
    )
    .filter((link: Link) => {
      // This is currently filtering out links that share a single position (showing only the first one that got the spot)
      return (
        visibleNodes.value.get(link.source.id) &&
        visibleNodes.value.get(link.target.id)
      )
    })
})

const viewportOffset = computed<number>(() => {
  return visibleRings.value.size * baseRadius
})

const viewportExtent = computed<[[number, number], [number, number]]>(() => {
  /**
   * So we don't forget this later:
   * The translation extent is the min coordinates of the translation axis;
   * In the negative direction, this means the negative radius of the outtermost circle (- 1 radius unit for padding)
   * In the positive direction, it's the radius of the outermost circle PLUS the circle offset, which is 1/2 the height in the Y direction and 1/2 the width in the X direction
   */
  const maxX = width.value + viewportOffset.value
  const maxY = height.value + viewportOffset.value
  return [
    [-viewportOffset.value, -viewportOffset.value],
    [maxX, maxY]
  ]
})

const miniMapStyle = computed<{
  width: string
  height: string
}>(() => {
  const x = viewportExtent.value[1][0] - viewportExtent.value[0][0]
  const y = viewportExtent.value[1][1] - viewportExtent.value[0][1]
  return {
    height: y + 'px',
    width: x + 'px'
  }
})

const miniMapViewportStyle = computed<{
  width: string
  height: string
}>(() => {
  return {
    height: height.value + 'px',
    width: width.value + 'px'
  }
})

/**
 * Methods
 */
const zoomed = ({
  transform
}: {
  transform: { x: number; y: number; k: number }
}): void => {
  const ts = `translate(${transform.x}px, ${transform.y}px) scale(${transform.k})`
  ringContainer.value?.style('transform', ts)
  edgeContainer.value?.style('transform', ts)
  nodeContainer.value?.style('transform', ts)

  if (miniViewport.value) {
    const x = 1 - transform.x + viewportOffset.value
    const y = 1 - transform.y + viewportOffset.value
    miniViewport.value.style.transform = `translate(${x}px, ${y}px) scale(${
      1 / transform.k
    })`
  }
}

const toggleTree = (node: SchematicNode) => {
  if (collapsedTrees.value.get(node.id)) {
    collapsedTrees.value.delete(node.id)
  } else {
    const tree = radial.value.traverse(node)
    collapsedTrees.value.set(node.id, tree)
  }
}

const updateRings = (): void => {
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
          .attr('stroke', 'rgba(0, 0, 0, 0.1)')
          .attr('stroke-width', 5)
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
}

const updateLinks = () => {
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

  const lineGenerator = (
    x0: number,
    y0: number,
    x1: number,
    y1: number,
    d: number
  ): [number, number] => {
    const distance = sqrt(pow(x1 - x0, 2) + pow(y1 - y0, 2))
    const t = d / distance
    const ex = (1 - t) * x0 + t * x1
    const ey = (1 - t) * y0 + t * y1
    return [ex, ey]
  }

  const pathGenerator = (d: Link, i: number) => {
    const path = d3.path()

    const sourceRing = radial.value.rings.get(d.source.ring)!
    const targetRing = radial.value.rings.get(d.target.ring)!
    const sourceLinks = sourceRing.links
    const sourceLinksIndex = sourceLinks.findIndex(
      (sl) => sl.source.id == d.source.id && sl.target.id == d.target.id
    )
    const cx = width.value / 2
    const cy = height.value / 2

    const distance = targetRing.radius - radial.value.baseRadius
    const distanceOffset =
      sourceLinksIndex *
      ((targetRing.radius - sourceRing.radius - 275) / sourceLinks.length)

    const tcx = d.target.cx
    const tcy = d.target.cy
    const targetAngle = d.target.radian
    const scx = d.source.cx
    const scy = d.source.cy
    const sourceAngle = d.source.radian

    let ex0, ey0
    if (sourceRing.radius == 0) {
      const [x, y] = lineGenerator(cx, cy, tcx, tcy, distance)
      ex0 = x
      ey0 = y
    } else {
      const [x, y] = lineGenerator(cx, cy, scx, scy, distance)
      ex0 = x
      ey0 = y
    }

    path.moveTo(scx, scy)
    path.lineTo(ex0, ey0)

    const [ex1, ey1] = lineGenerator(cx, cy, tcx, tcy, distance)

    if (tcx !== scx && tcy !== scy && sourceRing.radius !== 0) {
      path.arc(
        cx,
        cy,
        sourceRing.radius + 275 - distanceOffset,
        sourceAngle,
        targetAngle,
        sourceAngle > targetAngle
      )
    } else {
      path.moveTo(ex1, ey1)
    }

    path.lineTo(tcx, tcy)
    return path.toString()
  }

  const strokeWidthGenerator = (d: Link) => {
    const sourceRing = radial.value.rings.get(d.source.ring)!
    const targetRing = radial.value.rings.get(d.target.ring)!
    const sourceLinks = sourceRing.links

    const maxWidth =
      (targetRing.radius - sourceRing.radius) / sourceLinks.length

    return Math.min(5, maxWidth)
  }

  const opacityGenerator = (d: Link) => {
    if (!highlightedNode.value) return 1
    return d.source.id == highlightedNode.value.id ||
      d.target.id == highlightedNode.value.id
      ? 1
      : 0.2
  }

  const idGenerator = (d: Link) => d.source.id + '---' + d.target.id

  const strokeGenerator = (d: Link, i: number) => {
    return useLinearGradient ? `url("#${d.source.data.name + i}")` : null
  }

  const classGenerator = (d: Link) => {
    const opaqueStrokeClass = `${d.source.data.state.type.toLowerCase()}-stroke`
    const transparentStrokeClass = 'transparent'
    if (!highlightedNode.value) return opaqueStrokeClass
    return d.source.id == highlightedNode.value.id ||
      d.target.id == highlightedNode.value.id
      ? `${opaqueStrokeClass} highlighted`
      : transparentStrokeClass
  }

  edgeContainer.value
    ?.selectAll('path')
    .data(visibleLinks.value)
    .join(
      // enter
      (selection: any) =>
        selection
          .append('path')
          .attr('id', idGenerator)
          .attr('class', classGenerator)
          .style('stroke', strokeGenerator)
          .style('stroke-width', strokeWidthGenerator)
          .attr('d', pathGenerator)
          .style('opacity', opacityGenerator),
      // update
      (selection: any) =>
        selection
          .attr('id', idGenerator)
          .attr('class', classGenerator)
          .style('stroke', strokeGenerator)
          .style('stroke-width', strokeWidthGenerator)
          .attr('d', pathGenerator)
          .style('opacity', opacityGenerator),
      // exit
      (selection: any) => selection.remove()
    )
}

const updateAll = () => {
  updateRings()
  updateLinks()
}

const highlightNode = (item: SchematicNode): void => {
  if (highlightedNode.value?.id == item.id) highlightedNode.value = undefined
  else highlightedNode.value = item
  requestAnimationFrame(() => updateLinks())
}

const panToNode = (item: SchematicNode): void => {
  highlightNode(item)

  requestAnimationFrame(() => {
    const node = visibleNodes.value.get(item.id)
    if (!node) return
    ;(document.querySelector(`#node-${item.id}`) as HTMLElement)?.focus()

    const zoomIdentity = d3.zoomIdentity
      .translate(width.value / 2, height.value / 2)
      // .scale(1)
      .translate(-node.cx, -node.cy)

    d3.select('.schematic-svg')
      .transition()
      .duration(250)
      .call(zoom.value.transform, zoomIdentity)
  })
}

/**
 * Schematic refs
 */
const useLinearGradient: boolean = false
const height = ref<number>(0)
const width = ref<number>(0)
const baseRadius: number = 300
const highlightedNode = ref<SchematicNode>()

const collapsedTrees = ref<Map<string, Map<string, SchematicNode>>>(new Map())
const radial = ref<RadialSchematic>(new RadialSchematic())

const zoom = ref<d3.ZoomBehavior<any, any>>(d3.zoom())

/**
 * Watchers
 */
watch(
  () => props.items,
  (curr, prev) => {
    items.value = props.items
    radial.value.items(items.value)

    if (curr.length > 0 && prev.length == 0) {
      radial.value.center([width.value / 2, height.value / 2])
    }

    if (curr.length !== prev.length) {
      requestAnimationFrame(() => updateAll())
    } else {
      requestAnimationFrame(() => updateLinks())
    }
  }
)

watch(visibleRings, () => {
  zoom.value.translateExtent(viewportExtent.value)
  // d3.select('.schematic-svg')
  //   .transition()
  //   .duration(250)
  //   .call(zoom.value.transform, d3.zoomIdentity)
})

watch(visibleLinks, () => {
  requestAnimationFrame(() => updateAll())
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
    .translateExtent(viewportExtent.value)
    .scaleExtent([0.1, 1])
    // .filter((e: Event) => e?.type !== 'wheel' && e?.type !== 'dblclick') // Disables user mouse wheel and double click zoom in/out
    .on('zoom', zoomed)

  svg.value
    ?.attr('viewbox', `0, 0, ${width.value}, ${height.value}`)
    .call(zoom.value)

  updateAll()
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

  console.log(radial.value)

  createChart()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleWindowResize)
})
</script>

<style lang="scss" scoped>
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

  .mini-map {
    backdrop-filter: blur(1px);
    background-color: rgba(142, 160, 174, 0.1);
    border-radius: 40px;
    bottom: 0;
    overflow: hidden;
    transform: scale(0.05);
    right: 0;
    transform-origin: 100% 100%;
    z-index: 9999;

    .mini-map--viewport {
      background-color: rgba(142, 160, 174, 0.5);
      border-radius: 40px;
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
      opacity: 1;
      stroke-width: 20;
      stroke-opacity: 0.9;
      stroke-linejoin: round;

      &.transparent {
        stroke: #ccc;
      }

      &.highlighted {
        // filter: drop-shadow(0px 1px 2px rgba(0, 0, 0, 0.06))
        //   drop-shadow(0px 1px 3px rgba(0, 0, 0, 0.1));
      }
    }
  }

  .ring {
    pointer-events: none;
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
