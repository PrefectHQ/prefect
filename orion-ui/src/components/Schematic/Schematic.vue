<template>
  <div class="schematic-container" ref="container" @scroll="preventScroll">
    <svg ref="svg" class="schematic-svg">
      <defs id="defs" />
      <g id="edge-container" />
      <g id="ring-container" />
    </svg>

    <div class="node-container">
      <template
        v-for="[key, node] of visibleNodes"
        :id="`node-${key}`"
        :key="key"
      >
        <Node
          v-if="node.position?.nodes.size == 1"
          :node="node"
          :selected="selectedNodes.includes(node.id)"
          class="node position-absolute"
          :class="{
            transparent:
              selectedNodes.length > 0 &&
              !selectedNodes.includes(node.id) &&
              highlightedNode !== node.id,
            demphasized:
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
        <OverflowNode
          v-else
          class="position-absolute"
          :nodes="node.position?.nodes"
          :style="{ left: node.cx + 'px', top: node.cy + 'px' }"
          tabindex="0"
          @click="expandRing(node)"
        />
      </template>
    </div>

    <div class="mini-map-container position-absolute mr-2 mb-2">
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

      <div
        class="mini-map position-relative"
        @mousemove="dragViewport"
        @mouseleave="dragging = false"
      >
        <svg
          ref="mini-svg"
          class="minimap-schematic-svg"
          @click="panToLocation"
        >
          <g id="mini-ring-container" />
        </svg>

        <div
          ref="miniViewport"
          class="mini-map--viewport position-absolute"
          :style="miniMapViewportStyle"
          @mousedown="dragging = true"
          @mouseup="dragging = false"
        />
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import {
  ref,
  defineProps,
  computed,
  onMounted,
  onUnmounted,
  watch,
  reactive
} from 'vue'
import * as d3 from 'd3'
import { RadialSchematic } from './util'
import { pow, sqrt, pi, cos, sin } from './math'

import Node from './Node.vue'
import OverflowNode from './OverflowNode.vue'

import {
  Item,
  Link,
  SchematicNodes,
  SchematicNode,
  Rings,
  Ring,
  Links,
  Position
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
const miniSvg = ref<Selection>()
const defs = ref<Selection>()
const edgeContainer = ref<Selection>()
const ringContainer = ref<Selection>()
const miniRingContainer = ref<Selection>()
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

const viewportOffset = computed<number>(() => {
  const radii = [...visibleRings.value.entries()].map(([, ring]) => ring.radius)
  return Math.max(...radii, baseRadius * 2)
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

const scale = computed<number>(() => {
  const scale_ = 200 / (viewportOffset.value * 2.5)
  return scale_
})

const miniMapViewportStyle = computed<{
  width: string
  height: string
}>(() => {
  return {
    height: miniMapDimensions.value.height + 'px',
    width: miniMapDimensions.value.width + 'px'
  }
})

const miniMapDimensions = computed<{ width: number; height: number }>(() => {
  return {
    height: height.value * scale.value,
    width: width.value * scale.value
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

  k = transform.k
  x = transform.x
  y = transform.y

  if (miniViewport.value) {
    const x =
      (1 - transform.x / transform.k) * scale.value +
      100 -
      miniMapDimensions.value.width / 2
    const y =
      (1 - transform.y / transform.k) * scale.value +
      100 -
      miniMapDimensions.value.height / 2

    miniViewport.value.style.transform = `translate(${x}px, ${y}px) scale(${
      1 / transform.k
    })`
    miniViewport.value.style.borderRadius = `${Math.max(4 * transform.k, 4)}px`
  }
}

const expandRing = (node: SchematicNode) => {
  radial.value.expandRing(node.ring)
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

  type Arc = {
    start: number
    end: number
    radius: number
    state: string | null
  }

  const calculateArcSegment = (arc: Arc, scale: number = 1): string => {
    const r = arc.radius
    const cx = 100
    const cy = 100

    const path = d3.path()

    path.arc(cx, cy, r, arc.start, arc.end, false)
    return path.toString()
  }

  const generateArcs = ([, d]: [number, Ring]): Arc[] => {
    const arcs: Arc[] = []

    const r = d.radius
    const channel = 125

    const channelAngle = (channel * 360) / (2 * pi * r || 10)

    // Convert start/end angles to radians
    const startTheta = ((90 - channelAngle) * pi) / 180
    const endTheta = ((90 + channelAngle) * pi) / 180

    let theta = d.positions.get(d.positions.size - 1)?.radian || 0

    for (const [key, position] of d.positions) {
      const positionalArr = [...position.nodes.values()]
      const state = positionalArr?.[0]?.data?.state?.type?.toLowerCase()

      if (r == 0) {
        // This is only for the innermost ring for schematics with a single root node
        arcs.push({
          start: (115 * pi) / 180,
          end: (65 * pi) / 180,
          radius: baseRadius / 4,
          state: state || null
        })
      } else if (position.radian > startTheta && theta < endTheta) {
        arcs.push({
          start: theta,
          end: startTheta,
          radius: r,
          state: null
        })
        arcs.push({
          start: endTheta,
          end: position.radian,
          radius: r,
          state: state || null
        })
      } else {
        arcs.push({
          start: theta,
          end: position.radian,
          radius: r,
          state: state || null
        })
      }
      theta = position.radian
    }
    return arcs
  }

  ringContainer.value
    ?.selectAll('.ring')
    .data(visibleRings.value)
    .join(
      // enter
      (selection: any) => {
        const g = selection.append('g')
        g.attr('id', (d: any) => d.id)
        const arc = g.attr('class', 'ring').append('path')
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

  const classGenerator = (d: Arc): string => {
    const strokeClass = d.state ? `${d.state}-stroke` : ''
    return `mini-arc-segment ${strokeClass}`
  }

  miniRingContainer.value
    // ?.style(
    //   'transform',
    //   `translate(${60 * scale.value}px, ${60 * scale.value}px) scale(${
    //     scale.value
    //   })`
    // )
    ?.style('transform', `scale(${scale.value})`)
    .selectAll('.mini-arc-segment-group')
    .data(visibleRings.value)
    .join(
      // enter
      (selection: any) =>
        selection.append('g').attr('class', 'mini-arc-segment-group'),
      // update
      (selection: any) => selection,
      // exit
      (selection: any) => selection.remove()
    )
    .selectAll('.mini-arc-segment')
    .data((d: [number, Ring]) => generateArcs(d))
    .join(
      // enter
      (selection: any) =>
        selection
          .append('path')
          .attr('class', classGenerator)
          .attr('fill', 'transparent')
          .attr('stroke', 'rgba(0, 0, 0, 0.1)')
          .attr('stroke-width', 80)
          .attr('d', (d: Arc) => calculateArcSegment(d, scale.value)),
      (selection: any) =>
        selection
          .attr('class', classGenerator)
          .attr('d', (d: Arc) => calculateArcSegment(d, scale.value)),
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
    const classList = []
    const emphasized = isEmphasized(d)
    if (emphasized || (selectedNodes.length == 0 && !highlightedNode.value)) {
      classList.push(`${d.source.data.state.type.toLowerCase()}-stroke`)
    }
    if (visibleLinks.value.length < 100) classList.push('transition')
    return classList.join(' ')
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

const panToNode = (item: SchematicNode): void => {
  const node = visibleNodes.value.get(item.id)
  if (!node) return
  ;(document.querySelector(`#node-${item.id}`) as HTMLElement)?.focus()

  const zoomIdentity = d3.zoomIdentity
    .translate(width.value / 2, height.value / 2)
    // .scale(1)
    .translate(-node.cx, -node.cy)

  requestAnimationFrame(() => {
    d3.select('.schematic-svg')
      .transition()
      .duration(250)
      .call(zoom.value.transform, zoomIdentity)
  })
}

const panToLocation = (e: MouseEvent): void => {
  const rect = (e.target as Element)?.getBoundingClientRect()

  const x_ = (e.clientX - rect.left - 100) / scale.value
  const y_ = (e.clientY - rect.top - 100) / scale.value
  const zoomIdentity = d3.zoomIdentity.scale(k).translate(-x_, -y_)

  requestAnimationFrame(() => {
    d3.select('.schematic-svg')
      .transition()
      .duration(200)
      .call(zoom.value.transform, zoomIdentity)
  })
}

const dragViewport = (e: MouseEvent): void => {
  if (!dragging.value) return
  // We multiply the mouse movement by a multiplier equal to the inverse
  // of the scale applied to the minimap
  const x = e.movementX * -(1 / scale.value)
  const y = e.movementY * -(1 / scale.value)
  zoom.value.translateBy(d3.select('.schematic-svg'), x, y)
}

const reset = (): void => {
  selectedNodes.length = 0
}

const resetViewport = (): void => {
  d3.select('.schematic-svg')
    .transition()
    .ease(d3.easeQuadInOut)
    .duration(250)
    .call(zoom.value.transform, d3.zoomIdentity)
}

const zoomIn = (): void => {
  requestAnimationFrame(() => {
    zoom.value.scaleBy(
      d3
        .select('.schematic-svg')
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
        .select('.schematic-svg')
        .transition()
        .ease(d3.easeQuadInOut)
        .duration(250),
      0.65
    )
  })
}

/**
 * Schematic refs
 */
const height = ref<number>(0)
const width = ref<number>(0)
const baseRadius: number = 300
const highlightedNode = ref<string>()
const selectedNodes = reactive<string[]>([])
const dragging = ref<boolean>(false)
let k = 1,
  x = 0,
  y = 0

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

      resetViewport()
    }

    if (curr.length !== prev.length) {
      requestAnimationFrame(() => updateAll())
    } else {
      requestAnimationFrame(() => updateLinks())
    }
  }
)

watch(selectedNodes, () => {
  requestAnimationFrame(() => updateLinks())
})

watch(visibleRings, () => {
  // zoom.value.translateExtent(viewportExtent.value)
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
  miniSvg.value = d3.select('.minimap-schematic-svg')
  defs.value = d3.select('#defs')
  ringContainer.value = svg.value.select('#ring-container')
  miniRingContainer.value = miniSvg.value.select('#mini-ring-container')
  edgeContainer.value = svg.value.select('#edge-container')
  nodeContainer.value = d3.select('.node-container')

  // Note: we're applying a transform here which is the width of the side nav
  // and the height of the top nav multiplied by the scale; I'm not
  // entirely sure this is correct but it does have the desired outcome.
  // Ideally we wouldn't need to apply this but the graph itself
  // actually flows under both of those components which leads to a weird
  // offset in a true-to-scale representation of the minimap

  //translate(${60 * scale.value}px, ${60 * scale.value}px)
  miniRingContainer.value
    .attr('class', 'mini-ring-container')
    .style('transform', `scale(${scale.value})`)
  ringContainer.value.attr('class', 'ring-container')
  edgeContainer.value.attr('class', 'edge-container')

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

  miniSvg.value?.attr('viewbox', '0, 0, 200, 200')

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
@use '@prefecthq/miter-design/src/styles/abstracts/variables' as *;
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

  .mini-map-container {
    bottom: 0;
    right: 0;
    z-index: 9999999;

    .mini-map {
      backdrop-filter: blur(1px);
      filter: $drop-shadow-sm;
      background-color: rgba(244, 245, 247, 0.9);
      border-radius: 8px;
      overflow: hidden;
      height: 200px;
      width: 200px;

      .minimap-schematic-svg {
        cursor: pointer !important;
      }

      .mini-map--viewport {
        background-color: rgba(63, 150, 216, 0.2);
        border-radius: 8px;
        cursor: grab;
        transform-origin: center;
        z-index: 1;

        &:active {
          cursor: grabbing;
        }
      }
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

  .node {
    &.transparent {
      opacity: 0.65;
    }

    &.demphasized {
      opacity: 1;
      // background-color: red;
    }
  }
}
</style>

<style lang="scss">
.schematic-container {
  svg {
    path {
      fill: none;
      opacity: 1;
      stroke-linejoin: round;
    }
  }

  .edge-container {
    path {
      stroke: #ddd;

      &.transition {
        transition: opacity 100ms linear 0;
      }
    }
  }

  .ring {
    pointer-events: none;
  }

  .minimap-schematic-svg {
    .mini-ring-container {
      transform-origin: center;
      position: absolute;
    }

    .mini-arc-segment-group {
      pointer-events: none;
    }
  }
}
</style>
