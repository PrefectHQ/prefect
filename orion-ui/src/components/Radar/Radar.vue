<template>
  <div ref="container" class="radar" @scroll="preventScroll">
    <svg class="radar__canvas">
      <g class="radar__edge-container" />
      <g class="radar__ring-container" />
    </svg>

    <div class="radar__node-container">
      <template v-for="[key, node] of visibleNodes" :key="key">
        <component
          v-if="node.position?.nodes.size == 1"
          :is="
            node.data.state.state_details.child_flow_run_id
              ? 'radar-flow-run-node'
              : 'radar-node'
          "
          :id="`node-${key}`"
          :node="node"
          :selected="selectedNodes.includes(node.id)"
          class="radar__node position-absolute"
          :class="{
            'radar__node--transparent':
              selectedNodes.length > 0 &&
              !selectedNodes.includes(node.id) &&
              highlightedNode !== node.id,
            'radar__node--deemphasized':
              selectedNodes.length > 0 &&
              selectedNodes.some(
                (id) =>
                  node.upstreamNodes.get(id) || node.downstreamNodes.get(id)
              )
          }"
          :collapsed="collapsedTrees.get(key)"
          :style="{ left: node.cx + 'px', top: node.cy + 'px' }"
          tabindex="0"
          @toggle-tree="toggleTree"
          @click.stop="selectNode(node.id)"
          @keyup.space.enter="selectNode(node.id)"
          @mouseover="highlightNode(node.id)"
          @mouseout="highlightNode(node.id)"
        />
        <!-- @focus.self.stop="panToNode(node)" -->
        <radar-overflow-node
          v-else
          class="position-absolute"
          :nodes="node.position?.nodes"
          :style="{ left: node.cx + 'px', top: node.cy + 'px' }"
          tabindex="0"
          @click="expandRing(node)"
        />
      </template>
    </div>

    <div class="radar__minimap-controls-container position-absolute mr-2 mb-2">
      <div class="mb-1 d-flex align-center justify-end">
        <icon-button
          class="bg--white justify-self-start mr-auto"
          icon="pi-restart-line"
          @click="reset"
        />
        <icon-button
          class="bg--white mr-1"
          icon="pi-zoom-in-line"
          @click="zoomIn"
        />
        <icon-button
          class="bg--white mr-1"
          icon="pi-zoom-out-line"
          @click="zoomOut"
        />
        <icon-button
          class="bg--white"
          icon="pi-fullscreen-fill"
          @click="resetViewport"
        />
      </div>

      <div class="radar__minimap-container">
        <MiniRadar
          class="radar__minimap position-relative"
          :id="id"
          :transform="transform_"
          :collapsed-trees="collapsedTrees"
          :radar="radial"
          :height="height"
          :width="width"
          @drag-viewport="dragViewport"
          @pan-to-location="panToLocation"
        />
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted, onUnmounted, watch, reactive } from 'vue'
import * as d3 from 'd3'
import { ZoomTransform } from 'd3-zoom'
import { Radar } from './Radar'
import { pow, sqrt, pi, cos, sin } from './math'
import MiniRadar from './MiniRadar.vue'

import {
  Item,
  Link,
  RadarNodes,
  RadarNode,
  Rings,
  Ring,
  Links
} from '@/typings/radar'

const props = defineProps<{ items: Item[]; id: string }>()
const items = ref<Item[]>(props.items)

/**
 * Selection Refs
 */
type Selection = d3.Selection<SVGGElement, unknown, HTMLElement, any>

const container = ref<HTMLElement>()
const canvas = ref<Selection>()
const edgeContainer = ref<Selection>()
const ringContainer = ref<Selection>()
const nodeContainer = ref<Selection>()

/**
 * Computed
 */
const visibleNodes = computed<RadarNodes>(() => {
  const collapsed = [...collapsedTrees.value.entries()]
  return new Map(
    [...radial.value.nodes.entries()]
      .filter(([, node]) => collapsed.every(([, tree]) => !tree.get(node.id)))
      .filter(([, node]) => {
        // This is currently filtering out nodes that share a single position (showing only the first one that got the spot)
        const ring: Ring | undefined = radial.value.rings.get(node.ring)
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
  transform_.value = transform
}

const expandRing = (node: RadarNode) => {
  radial.value.expandRing(node.ring)
}

const toggleTree = (node: RadarNode) => {
  if (collapsedTrees.value.get(node.id)) {
    collapsedTrees.value.delete(node.id)
  } else {
    const tree = radial.value.traverse(node)
    collapsedTrees.value.set(node.id, tree)
  }
}

const updateRings = (): void => {
  const polarToCartesian = (
    cx: number,
    cy: number,
    radius: number,
    angle: number
  ): [number, number] => {
    const radians = angle * (pi / 180)
    const x = cx + radius * cos(radians) || 0
    const y = cy + radius * sin(radians) || 0
    return [x, y]
  }

  const calculateArc = ([, d]: [number, Ring], scale: number = 1) => {
    const r = d.radius
    const channel = 125
    const theta = (channel * 360) / (2 * pi * r)

    const cx = (width.value / 2) * scale
    const cy = (height.value / 2) * scale
    const [x0, y0] = polarToCartesian(cx, cy, r, 90 - theta) // ~45
    const [x1, y1] = polarToCartesian(cx, cy, r, 90 + theta) // ~135
    return `M ${x0} ${y0} A${d.radius} ${d.radius} 0 1 0 ${x1} ${y1}`
  }

  ringContainer.value
    ?.selectAll('.radar__ring')
    .data(visibleRings.value)
    .join(
      // enter
      (selection: any) => {
        const g = selection.append('g')
        g.attr('id', (d: any) => d.id)
        const arc = g.attr('class', 'radar__ring').append('path')
        arc
          .attr('id', ([key]: [number, Ring]) => key)
          .attr('d', (d: [number, Ring]) => calculateArc(d, 1))
          .style('opacity', 1)
          .attr('fill', 'transparent')
          .attr('stroke', 'rgba(0, 0, 0, 0.03)')
          .attr('stroke-width', 80)
        return g
      },
      // update
      (selection: any) => {
        const arc = selection.select('path')
        arc
          .attr('id', ([key]: [number, Ring]) => key)
          .attr('d', (d: [number, Ring]) => calculateArc(d, 1))
        return selection
      },
      // exit
      (selection: any) => selection.remove()
    )
}

const updateLinks = () => {
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

    const south = pi / 2
    const north = (3 * pi) / 2
    const east = 0

    const sourceRing = radial.value.rings.get(d.source.ring)!
    const targetRing = radial.value.rings.get(d.target.ring)!
    const targetPreviousRing = radial.value.rings.get(d.target.ring - 1)!
    const sourceNextRing = radial.value.rings.get(d.source.ring + 1)!
    const sourceLinks = sourceRing.links
    const sourceLinksIndex = sourceLinks.findIndex(
      (sl) => sl.source.id == d.source.id && sl.target.id == d.target.id
    )
    const cx = width.value / 2
    const cy = height.value / 2

    const distance = (targetRing.radius - sourceRing.radius) / 2
    const distanceArea = distance / sourceLinks.length
    const distanceOffset = sourceLinksIndex * distanceArea

    const tcx = d.target.cx
    const tcy = d.target.cy
    const targetAngle = d.target.radian
    const scx = d.source.cx
    const scy = d.source.cy
    const sourceAngle = d.source.radian

    let ex0, ey0
    if (sourceRing.radius == 0) {
      const [x, y] = lineGenerator(
        cx,
        cy,
        tcx,
        tcy,
        targetRing.radius - sourceRing.radius
      )
      ex0 = x
      ey0 = y
    } else if (d.target.ring - d.source.ring === 1) {
      const [x, y] = lineGenerator(
        cx,
        cy,
        scx,
        scy,
        sourceRing.radius + distance * 1.25 - distanceOffset
      )
      ex0 = x
      ey0 = y
    } else {
      const [x, y] = lineGenerator(
        cx,
        cy,
        scx,
        scy,
        sourceRing.radius + (sourceNextRing.radius - sourceRing.radius) / 2
      )
      ex0 = x
      ey0 = y
    }

    // Move the pointer to the source node
    path.moveTo(scx, scy)

    // Start jump-ring edge traveral
    if (d.target.ring - d.source.ring > 1) {
      if (sourceRing.radius !== 0) {
        // Draw a line some distance out from the source node
        path.lineTo(ex0, ey0)

        // Draw an arc to the south channel
        path.arc(
          cx,
          cy,
          sourceRing.radius + (sourceNextRing.radius - sourceRing.radius) / 2,
          sourceAngle,
          south,
          sourceAngle < north && sourceAngle > east
        )
      }

      const exitY =
        targetPreviousRing.radius +
        (targetRing.radius - targetPreviousRing.radius) / 2

      const [x, y] = lineGenerator(
        cx,
        cy,
        cx,
        exitY,
        targetPreviousRing.radius +
          (targetRing.radius - targetPreviousRing.radius) / 2
      )

      // Draw a line to the appropriate channel exit
      path.lineTo(x, y)

      // Draw an arc to the target radian
      path.arc(
        cx,
        cy,
        targetPreviousRing.radius +
          (targetRing.radius - targetPreviousRing.radius) / 2,
        south,
        targetAngle,
        targetAngle > north || targetAngle < south
      )

      // End jump-ring edge traveral
    } else {
      // Start intra-ring edge traveral
      // Draw a line some distance out from the source node
      path.lineTo(ex0, ey0)

      const [ex1, ey1] = lineGenerator(
        cx,
        cy,
        tcx,
        tcy,
        targetRing.radius - sourceRing.radius
      )

      if (tcx !== scx && tcy !== scy && sourceRing.radius !== 0) {
        const c = pi / 2
        path.arc(
          cx,
          cy,
          sourceRing.radius + distance * 1.25 - distanceOffset,
          sourceAngle,
          targetAngle,
          (sourceAngle > c && targetAngle > c && targetAngle < sourceAngle) ||
            (sourceAngle < c && (targetAngle > c || targetAngle < sourceAngle))
        )
      } else {
        path.moveTo(ex1, ey1)
      }

      // End intra-ring edge traveral
    }

    // Draw line to target
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

  const isEmphasized = (d: Link) => {
    const isSelected =
      selectedNodes.includes(d.source.id) || selectedNodes.includes(d.target.id)
    const isHighlighted =
      highlightedNode.value &&
      (d.source.id == highlightedNode.value ||
        d.target.id == highlightedNode.value)

    return isSelected || isHighlighted
  }

  const opacityGenerator = (d: Link) => {
    if (!highlightedNode.value && selectedNodes.length === 0) return 1
    if (isEmphasized(d)) return 1
    return 0.2
  }

  const idGenerator = (d: Link) => d.source.id + '---' + d.target.id

  const classGenerator = (d: Link) => {
    const classList = ['radar__edge']
    const emphasized = isEmphasized(d)
    if (emphasized || (selectedNodes.length == 0 && !highlightedNode.value)) {
      classList.push(`${d.source.data.state.type.toLowerCase()}-stroke`)
    }
    if (visibleLinks.value.length < 100)
      classList.push('radar__edge--transition')
    return classList.join(' ')
  }

  edgeContainer.value
    ?.selectAll('.radar__edge')
    .data(visibleLinks.value)
    .join(
      // enter
      (selection: any) =>
        selection
          .append('path')
          .attr('id', idGenerator)
          .attr('class', classGenerator)
          .style('stroke-width', strokeWidthGenerator)
          .attr('d', pathGenerator)
          .style('opacity', opacityGenerator),
      // update
      (selection: any) =>
        selection
          .attr('id', idGenerator)
          .attr('class', classGenerator)
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

const highlightNode = (id: string): void => {
  if (highlightedNode.value == id) highlightedNode.value = undefined
  else highlightedNode.value = id
  requestAnimationFrame(() => updateLinks())
}

const selectNode = (id: string): void => {
  const index = selectedNodes.indexOf(id)
  if (index > -1) {
    selectedNodes.splice(index, 1)
  } else {
    selectedNodes.push(id)
  }
}

const panToNode = (item: RadarNode): void => {
  const node = visibleNodes.value.get(item.id)
  if (!node) return
  ;(document.querySelector(`#node-${item.id}`) as HTMLElement)?.focus()

  const zoomIdentity = d3.zoomIdentity
    .translate(width.value / 2, height.value / 2)
    .translate(-node.cx, -node.cy)

  requestAnimationFrame(() => {
    d3.select('.radar__canvas')
      .transition()
      .duration(250)
      .call(zoom.value.transform, zoomIdentity)
  })
}

const panToLocation = (zoomIdentity: ZoomTransform): void => {
  requestAnimationFrame(() => {
    d3.select('.radar__canvas')
      .transition()
      .duration(200)
      .call(zoom.value.transform, zoomIdentity)
  })
}

const dragViewport = ({ x, y }: { x: number; y: number }): void => {
  zoom.value.translateBy(d3.select('.radar__canvas'), x, y)
}

const reset = (): void => {
  selectedNodes.length = 0
}

const resetViewport = (): void => {
  d3.select('.radar__canvas')
    .transition()
    .ease(d3.easeQuadInOut)
    .duration(250)
    .call(zoom.value.transform, d3.zoomIdentity)
}

const zoomIn = (): void => {
  requestAnimationFrame(() => {
    zoom.value.scaleBy(
      d3
        .select('.radar__canvas')
        .transition()
        .ease(d3.easeQuadInOut)
        .duration(250),
      1.35
    )
  })
}

const zoomOut = (): void => {
  requestAnimationFrame(() => {
    zoom.value.scaleBy(
      d3
        .select('.radar__canvas')
        .transition()
        .ease(d3.easeQuadInOut)
        .duration(250),
      0.65
    )
  })
}

/**
 * Radar refs
 */
const height = ref<number>(0)
const width = ref<number>(0)
const baseRadius: number = 300
const highlightedNode = ref<string>()
const selectedNodes = reactive<string[]>([])
const transform_ = ref<{ x: number; y: number; k: number }>({
  x: 0,
  y: 0,
  k: 1
})

const collapsedTrees = ref<Map<string, Map<string, RadarNode>>>(new Map())
const radial = ref<Radar>(new Radar())

const zoom = ref<d3.ZoomBehavior<any, any>>(d3.zoom())

/**
 * Watchers
 */
watch(
  () => [props.items, props.id],
  (curr, prev) => {
    const [currItems, currId] = curr
    const [prevItems, prevId] = prev

    items.value = props.items

    radial.value.items(items.value)

    if ((currItems.length > 0 && prevItems.length == 0) || currId !== prevId) {
      radial.value.center([width.value / 2, height.value / 2])
      selectedNodes.length = 0

      resetViewport()
    }

    if (currItems.length !== prevItems.length || currId !== prevId) {
      requestAnimationFrame(() => updateAll())
    } else {
      requestAnimationFrame(() => updateLinks())
    }
  }
)

watch(selectedNodes, () => {
  requestAnimationFrame(() => updateLinks())
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
  canvas.value = d3.select('.radar__canvas')
  ringContainer.value = canvas.value.select('.radar__ring-container')
  edgeContainer.value = canvas.value.select('.radar__edge-container')
  nodeContainer.value = d3.select('.radar__node-container')
  zoom.value = d3
    .zoom()
    .extent([
      [0, 0],
      [width.value, height.value]
    ])
    // .translateExtent(viewportExtent.value)
    // .scaleExtent([0.0001, 1])
    // .filter((e: Event) => e?.type !== 'wheel' && e?.type !== 'dblclick') // Disables user mouse wheel and double click zoom in/out
    .on('zoom', zoomed)

  canvas.value
    ?.attr('viewbox', `0, 0, ${width.value}, ${height.value}`)
    .call(zoom.value)

  updateAll()
  resetViewport()
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

<style lang="scss" scoped>
@use '@prefecthq/miter-design/src/styles/abstracts/variables' as *;
.radar {
  height: 100vh;
  max-height: 100vh;
  max-width: 100%;
  overflow: hidden;
  position: fixed;
  width: 100%;

  &__canvas {
    cursor: grab;
    height: inherit;
    left: 0;
    overflow: hidden;
    top: 0;
    width: inherit;

    &:active {
      cursor: grabbing;
    }
  }

  &__minimap-controls-container {
    bottom: 0;
    right: 0;
    z-index: 1;
  }

  &__minimap-container {
    backdrop-filter: blur(1px);
    background-color: rgba(244, 245, 247, 0.9);
    border-radius: 8px;
    filter: $drop-shadow-sm;
    height: 200px;
    overflow: hidden;
    width: 200px;
  }

  &__node-container {
    left: 0;
    pointer-events: none;
    position: absolute;
    top: 0;
    transform-origin: 0 0;
    user-select: none;
    z-index: 0;
  }

  &__node {
    &--transparent {
      opacity: 0.65;
    }

    &--deemphasized {
      opacity: 1;
    }
  }
}
</style>

<style lang="scss">
.radar {
  &__edge {
    fill: none;
    opacity: 1;
    stroke: #ddd;
    stroke-linejoin: round;

    &--transition {
      transition: opacity 100ms linear 0;
    }
  }

  &__ring {
    pointer-events: none;
  }
}
</style>
