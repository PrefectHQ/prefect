<template>
  <div class="schematic-container" ref="container" @scroll="preventScroll">
    <svg ref="svg" class="schematic-svg">
      <defs id="defs" />
    </svg>

    <div class="node-container">
      <div
        v-for="[key, node] of visibleNodes"
        :id="`node-${key}`"
        :key="key"
        :style="{ left: node.cx + 'px', top: node.cy + 'px' }"
        class="node d-flex align-stretch justify-start"
        :class="node.data.state.toLowerCase() + '-border'"
        tabindex="0"
        @focus.self="panToNode(node)"
      >
        <div
          class="d-flex align-center justify-center border px-1"
          :class="[
            node.data.state.toLowerCase() + '-bg',
            node.data.state.toLowerCase() + '-border'
          ]"
        >
          <i class="pi text--white pi-lg" :class="iconMap(node.data.state)" />
        </div>

        <div class="d-flex align-center justify-center px-1">
          <div class="text-truncate" style="width: 110px">
            {{ node.data.name }} - {{ node.ring }}
          </div>

          <div
            v-if="node.downstreamNodes.size > 0"
            class="collapse-button"
            tabindex="-1"
            @click.stop="toggleTree(node)"
          >
            <i
              class="pi pi-lg"
              :class="
                collapsedTrees.get(key)
                  ? 'pi-Small-Arrows-Separating'
                  : 'pi-Small-Arrows-Joining'
              "
            />
          </div>

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
    </div>
  </div>
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import { ref } from 'vue'
import * as d3 from 'd3'
import { RadialSchematic } from './util'
import { curveMetro } from './curveMetro'
import { curveMiter } from './curveMiter'

import {
  Item,
  Link,
  SchematicNodes,
  SchematicNode,
  Rings,
  Ring,
  Links
} from '@/types/schematic'

class Props {
  items = prop<Item[]>({ required: true })
}

@Options<Schematic>({
  watch: {
    items(val) {
      this.radial.center([this.width / 2, this.height / 2]).items(val)
      requestAnimationFrame(() => this.updateCanvas())
    },
    visibleRings() {
      this.zoom.scaleExtent([this.scaleExtentLower, 1])
    },
    visibleLinks() {
      requestAnimationFrame(() => this.updateCanvas())
    }
  }
})
export default class Schematic extends Vue.with(Props) {
  container = ref<HTMLElement>() as unknown as HTMLElement

  svg: d3.Selection<SVGGElement, unknown, HTMLElement, any> =
    null as unknown as d3.Selection<SVGGElement, unknown, HTMLElement, any>

  defs: d3.Selection<SVGGElement, unknown, HTMLElement, any> =
    null as unknown as d3.Selection<SVGGElement, unknown, HTMLElement, any>

  edgeContainer: d3.Selection<SVGGElement, unknown, HTMLElement, any> =
    null as unknown as d3.Selection<SVGGElement, unknown, HTMLElement, any>

  ringContainer: d3.Selection<SVGGElement, unknown, HTMLElement, any> =
    null as unknown as d3.Selection<SVGGElement, unknown, HTMLElement, any>

  nodeContainer: d3.Selection<SVGGElement, unknown, HTMLElement, any> =
    null as unknown as d3.Selection<SVGGElement, unknown, HTMLElement, any>

  zoom: d3.ZoomBehavior<any, any> = null as unknown as d3.ZoomBehavior<any, any>

  useLinearGradient: boolean = false

  height: number = 0
  width: number = 0

  baseRadius: number = 300
  startAngle: number = 0

  collapsedTrees: Map<string, Map<string, SchematicNode>> = new Map()

  radial: RadialSchematic = new RadialSchematic()

  line = d3.line().curve(curveMetro)

  get visibleRings(): Rings {
    const rings = new Set(
      [...this.visibleNodes.entries()].map(([key, node]) => node.ring)
    )
    return new Map(
      [...this.radial.rings.entries()].filter(([key, node]) => rings.has(key))
    )
  }

  // TODO: Is this the correct access pattern?
  get visibleNodes(): SchematicNodes {
    const collapsed = [...this.collapsedTrees.entries()]
    return new Map(
      [...this.radial.nodes.entries()].filter(([key, node]) =>
        collapsed.every(([_key, tree]) => !tree.get(node.id))
      )
    )
  }

  get visibleLinks(): Links {
    const collapsed = [...this.collapsedTrees.entries()]
    return this.radial.links.filter((link) =>
      collapsed.every(([_key, tree]) => !tree.get(link.target.id))
    )
  }

  get scaleExtentLower(): number {
    return (
      (1 / (this.radial.rings.size * this.baseRadius * 3)) *
      Math.max(this.height, this.width)
    )
  }

  iconMap(state: string) {
    return `pi-${state.toLowerCase()}`
  }

  toggleTree(node: SchematicNode) {
    if (this.collapsedTrees.get(node.id)) {
      this.collapsedTrees.delete(node.id)
    } else {
      const tree = this.radial.traverse(node)
      this.collapsedTrees.set(node.id, tree)
    }
  }

  zoomed({ transform }: any) {
    this.ringContainer?.attr('transform', transform)
    this.edgeContainer?.attr('transform', transform)

    this.nodeContainer?.style(
      'transform',
      `translate(${transform.x}px, ${transform.y}px) scale(${transform.k})`
    )
  }

  createChart() {
    this.svg = d3.select('.schematic-svg')
    this.defs = d3.select('#defs')

    this.zoom = d3
      .zoom()
      .extent([
        [0, 0],
        [this.width, this.height]
      ])
      .scaleExtent([this.scaleExtentLower, 1])
      // .filter((e: Event) => e?.type !== 'wheel' && e?.type !== 'dblclick') // Disables user mouse wheel and double click zoom in/out
      .on('zoom', this.zoomed)

    this.svg
      ?.attr('viewbox', `0, 0, ${this.width}, ${this.height}`)
      .call(this.zoom)

    this.ringContainer = this.svg.append('g')
    this.edgeContainer = this.svg.append('g')
    this.nodeContainer = d3.select('.node-container')

    this.ringContainer.attr('class', 'ring-container')
    this.edgeContainer.attr('class', 'edge-container')

    this.updateCanvas()
  }

  updateCanvas(): void {
    this.ringContainer
      .selectAll('.ring')
      .data(this.visibleRings)
      .join(
        // enter
        (selection: any) => {
          const g = selection.append('g')
          g.attr('id', (d: any) => d.id)
          const circle = g.attr('class', 'ring').append('circle')
          circle
            .attr('cx', this.width / 2)
            .attr('cy', this.height / 2)
            .attr('id', ([key, d]: [number, Ring]) => key)
            .attr('r', ([key, d]: [number, Ring]) => d.radius)
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
            .attr('cx', this.width / 2)
            .attr('cy', this.height / 2)
            .attr('id', ([key, d]: [number, Ring]) => key)
            .attr('r', ([key, d]: [number, Ring]) => d.radius)
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

    if (this.useLinearGradient) {
      // An alternative to using defs is to only use the edges
      // but add an animated portion to the actual element
      // ... that will likely be more performant
      this.defs
        .selectAll('linearGradient')
        .data(this.visibleLinks)
        .join(
          // enter
          (selection: any) => {
            const g = selection.append('linearGradient')
            g.attr('id', (d: Link, i: number) => d.source.data.name + i)
              .attr(
                'class',
                (d: Link) => `${d.source.data.state.toLowerCase()}-text`
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
                (d: Link) => `${d.source.data.state.toLowerCase()}-text`
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

    this.edgeContainer
      ?.selectAll('path')
      .data(this.visibleLinks)
      .join(
        // enter
        (selection: any) =>
          selection
            .append('path')
            .attr('id', (d: Link) => d.source.id + '-' + d.target.id)
            .attr(
              'class',
              (d: Link) => `${d.source.data.state.toLowerCase()}-stroke`
            )
            .style('stroke', (d: Link, i: number) =>
              this.useLinearGradient
                ? `url("#${d.source.data.name + i}")`
                : null
            )
            .style('stroke-width', (d: Link) =>
              d.source.data.state == 'pending' ? 5 : 20
            )
            .attr('d', (d: Link) =>
              this.line([
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
              (d: Link) => `${d.source.data.state.toLowerCase()}-stroke`
            )
            .style('stroke', (d: Link, i: number) =>
              this.useLinearGradient
                ? `url("#${d.source.data.name + i}")`
                : null
            )
            .style('stroke-width', (d: Link) =>
              d.source.data.state == 'pending' ? 5 : 20
            )
            .attr('d', (d: Link) =>
              this.line([
                [d.source.cx, d.source.cy],
                [d.target.cx, d.target.cy]
              ])
            )
            .style('opacity', 1),
        // exit
        (selection: any) => selection.remove()
      )
  }

  handleWindowResize() {
    this.height = this.container.offsetHeight
    this.width = this.container.offsetWidth
  }

  panToNode(item: Item | SchematicNode) {
    const node = this.visibleNodes.get(item.id)

    if (!node) return
    ;(document.querySelector(`#node-${item.id}`) as HTMLElement)?.focus()

    const zoomIdentity = d3.zoomIdentity
      .translate(this.width / 2, this.height / 2)
      .scale(1)
      .translate(-node.cx, -node.cy)

    d3.select('.schematic-svg')
      .transition()
      .duration(250)
      .call(this.zoom.transform, zoomIdentity)
  }

  // This is used to prevent scrolling of the container when
  // an out of view node is focused... we handle that with a transform event
  // to maintain state with the d3 elements
  preventScroll(e: Event) {
    e.preventDefault()
    if (!this.container) return
    this.container.scrollTop = 0
    this.container.scrollLeft = 0
  }

  mounted() {
    this.handleWindowResize()
    window.addEventListener('resize', this.handleWindowResize)

    this.radial.center([this.width / 2, this.height / 2]).items(this.items)
    this.createChart()
  }

  beforeDestroy() {
    window.removeEventListener('resize', this.handleWindowResize)
  }
}
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
}

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
  height: 53px;
  pointer-events: all;
  transition: top 150ms, left 150ms, transform 150ms, box-shadow 50ms;
  transform: translate(-50%, -50%);
  width: 188px;

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

  .collapse-button {
    border-radius: 50%;
    height: 20px;
    text-align: center;
    width: 20px;

    &:hover {
      background-color: var(--grey-5);
    }

    > i {
      color: rgba(0, 0, 0, 0.3);
    }
  }
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
