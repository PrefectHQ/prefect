<script>
import * as d3_base from 'd3'
import { event } from 'd3-selection'
import { zoom } from 'd3-zoom'
import * as d3_dag from 'd3-dag'
import uniqueId from 'lodash.uniqueid'
import SchematicNode from '@/components/Schematics/Schematic-Node'
import {
  curveMetro,
  makeQuadraticBezierPoints,
  isDiagonal
} from '@/utils/curveMetro'
import { STATE_COLORS } from '@/utils/states'
import { Tree } from '@/utils/Tree'

// Add our custom curve to d3 base
// and then merges the libraries together into one
// access point
const d3 = Object.assign({}, d3_base, d3_dag, { curveMetro: curveMetro })

export default {
  components: {
    SchematicNode
  },
  props: {
    devToolbar: { type: Boolean, required: false, default: () => false },
    hideControls: { type: Boolean, required: false, default: () => false },
    showCards: { type: Boolean, required: false, default: () => true },
    tasks: { type: Array, required: true }
  },
  data() {
    return {
      id: uniqueId('schematic'),
      canvas: null,
      canvasBbox: { top: 0, left: 0, right: 0, bottom: 0 },
      collapsed: true,
      context: null,
      createdBbox: false,
      curve: 'curveMetro',
      custom: null,
      customBase: null,
      dag: null,
      defaultEdgeColor: { r: 132, g: 132, b: 132, a: 1 },
      defaultArrowColor: { r: 132, g: 132, b: 132, a: 1 },
      defaultNodeColor: { r: 0, g: 117, b: 184, a: 0.25 },
      edgeColorUpstream: { r: 255, g: 238, b: 88, a: 0.7 },
      edgeColorDownstream: { r: 249, g: 168, b: 37, a: 0.7 },
      edgeColor: null,
      fadedNodeColor: { r: 189, g: 189, b: 189, a: 1 },
      flow: null,
      globalGroup: null,
      hasFit: false,
      height: 1250,
      labels: null,
      layout: null,
      layoutPlan: 'sugiyama',
      line: null,
      loading: false,
      mappedTasks: {},
      nodes: null,
      nodeColor: null,
      nodeData: [],
      painting: false,
      path: null,
      scaledZoom: null,
      selectedTaskId: this.$route.query.schematic
        ? this.$route.query.schematic
        : null,
      showEdgeColorSwatch: false,
      showNodeColorSwatch: false,
      showLabels: false,
      size: 0,
      transitionDuration: 250,
      transformEventK: 1,
      transformEventX: 0,
      transformEventY: 0,
      tree: null,
      width: 1250
    }
  },
  computed: {
    canvasStyle() {
      return {
        opacity: this.loading ? 1 : 0
      }
    },
    color: {
      get() {
        return this.showNodeColorSwatch
          ? this.nodeColor
            ? this.nodeColor
            : this.defaultNodeColor
          : this.edgeColor
          ? this.edgeColor
          : this.defaultEdgeColor
      },
      set(val) {
        this[this.showNodeColorSwatch ? 'nodeColor' : 'edgeColor'] = val
      }
    },
    nodeDataGroupTranslate() {
      return {
        opacity: this.loading ? 1 : 0,
        transform: `translate(${this.transformEventX}px, ${this.transformEventY}px) scale(${this.transformEventK})`
      }
    }
  },
  watch: {
    tasks() {
      if (!this.canvas) this.createCanvas()
      this.updateDag(this.tasks)
    }
  },
  mounted() {
    this.layout = null
    this.createCanvas()
    this.updateDag(this.tasks)
  },
  methods: {
    _zoomed() {
      let zoomEvent = event

      this.context.clearRect(0, 0, this.width, this.height)

      if (zoomEvent && zoomEvent.sourceEvent && zoomEvent.sourceEvent.ctrlKey) {
        if (zoomEvent.sourceEvent.deltaY > 0) {
          zoomEvent.transform.k =
            zoomEvent.transform.k - zoomEvent.transform.k * 0.03
        } else if (zoomEvent && zoomEvent.sourceEvent.deltaY < 0) {
          zoomEvent.transform.k =
            zoomEvent.transform.k + zoomEvent.transform.k * 0.03
        }
      }
      this.transform = zoomEvent.transform
      this.transformEventK = zoomEvent.transform.k
      this.transformEventX = zoomEvent.transform.x
      this.transformEventY = zoomEvent.transform.y
      this.drawCanvas(this.transform)
    },
    _zoomIn() {
      if (this.transform.k < 0.01) return
      let scaleBy = this.transform.k * 1.5,
        transform = this.transform.scale(scaleBy)
      this.canvas
        .transition()
        .duration(500)
        .call(
          this.scaledZoom.transform,
          d3.zoomIdentity.translate(transform.x, transform.y).scale(scaleBy)
        )
    },
    _zoomOut() {
      if (this.transform.k > 10) return
      let scaleBy = this.transform.k / 1.5,
        transform = this.transform.scale(scaleBy)
      this.canvas
        .transition()
        .duration(500)
        .call(
          this.scaledZoom.transform,
          d3.zoomIdentity.translate(transform.x, transform.y).scale(scaleBy)
        )
    },
    createCanvas() {
      this.canvas = d3.select(`#${this.id}`)

      let parent = this.canvas.select(function() {
        return this.parentNode
      })

      let computedStyle = window.getComputedStyle(parent._groups[0][0], null)

      let paddingLeft = parseFloat(
          computedStyle.getPropertyValue('padding-left')
        ),
        paddingRight = parseFloat(
          computedStyle.getPropertyValue('padding-right')
        ),
        paddingTop = parseFloat(computedStyle.getPropertyValue('padding-top')),
        paddingBottom = parseFloat(
          computedStyle.getPropertyValue('padding-left')
        )
      this.height =
        parent._groups[0][0].clientHeight - paddingTop - paddingBottom

      this.width = parent._groups[0][0].clientWidth - paddingLeft - paddingRight

      this.canvas.attr('width', this.width).attr('height', this.height)
      this.context = this.canvas.node().getContext('2d')
      this.customBase = document.createElement('custom')
      this.custom = d3.select(this.customBase)

      // Have to add this because the normal d3 wheel event
      // isn't being captured for some reason
      const filter = () => {
        return event.isTrusted
      }

      this.scaledZoom = zoom()
        .on('zoom', this._zoomed)
        .filter(filter)

      this.canvas.call(this.scaledZoom)
    },
    updateDag(tasks) {
      if (tasks.length === 0) return

      this.mappedTasks = {}

      this.painting = true
      let preStratify = tasks
        .filter(task => {
          if (!task.task) return true

          if (task.map_index > -1) {
            this.mappedTasks[task.task.id]
              ? this.mappedTasks[task.task.id].push(task)
              : (this.mappedTasks[task.task.id] = [task])
          }
          return task.map_index === -1
        })
        .map(task => {
          let parsedTask = task.task ? task.task : task

          let child = {
            ...task,
            ...parsedTask
          }

          if (parsedTask.upstream_edges.length) {
            child.parentIds = parsedTask.upstream_edges.map(
              edge => edge.upstream_task.id
            )
          } else {
            child.parentIds = []
          }
          return child
        })

      this.dag = d3.dagStratify()(preStratify)

      let heightRatio = 1
      this.dag.each(node => (node.heightRatio = heightRatio))

      if (!this.layout) {
        this.tree = new Tree(Object.assign({}, this.dag))
        this.size =
          this.tree.height > this.tree.width
            ? this.tree.height
            : this.tree.width

        let ratio = [this.tree.width * 700, this.tree.height * 300]

        // arquint - the layout algorithm of the graph - allows for node heights
        // size - array of width/height
        // decross - the amount of crossing edges that will be present in the
        //           layout; in order of speed (slowest to fastest):
        //              - decrossOpt (don't use this, it's v v slow for large graphs)
        //              - decrossTwoLayer().order(d3.twolayerOpt())
        //              - decrossTwoLayer
        // columnWidth - function should return a number, ex: () => 1
        // columnSeparation - space between columns; function should return a number, ex: () => 1
        // interLayerSeparation - vertical distance between layers
        // layering - node layer assignment (slowest to fastest):
        //              - layeringSimplex
        //              - layeringCoffmanGraham
        //              - layeringTopological
        //              - layeringLongestPath().topDown(false)
        //              - layeringLongestPath
        // columnAssignment - node column assignment:
        //             Simple Left     - columnSimpleLeft
        //             Simple Center   - columnSimpleCenter
        //             Adjacent Left   - columnAdjacent
        //             Adjacent Center - columnAdjacent.center(true)
        //             Complex Left    - columnComplex
        //             Complex Center  - columnComplex.center(true)
        // column2Coord(d3.column2CoordRect()) - converts the column assignment of each node to actual x0 and x1 coordinates
        // coord - coordinate assignment (slowest to fastest):
        //             Vertical          - coordVert
        //             Minimum Curves    - coordMinCurve
        //             Greedy            - coordGreedy
        //             Center            - coordCenter
        //

        if (this.layoutPlan == 'sugiyama') {
          this.layout = d3
            .sugiyama()
            .size(ratio)
            .layering(d3.layeringLongestPath())
            .decross(d3.decrossTwoLayer())
            .coord(d3.coordCenter())
            .separation((a, b) => {
              return a.data && b.data ? 200 : 100
            })
        } else if (this.layoutPlan == 'arquint') {
          this.layout = d3
            .arquint()
            .size(ratio)
            .layering(d3.layeringLongestPath())
            .decross(d3.decrossTwoLayer())
            .columnAssignment(d3.columnComplex().center(true))
            .column2Coord(d3.column2CoordRect())
            .interLayerSeparation(() => 96)
            .columnWidth(() => 500)
            .columnSeparation(() => 100)
        }
      }

      this.layout(this.dag)

      this.scaledZoom.scaleExtent([1 / this.size, 2])

      this.nodeData = this.dag.descendants()

      this.updateEdges()
      this.updateNodes()
      // this.labelNodes()
      let t = d3.timer(elapsed => {
        this.drawCanvas(d3.zoomIdentity)

        this.canvas.call(
          this.scaledZoom.transform,
          d3.zoomIdentity
            .translate(this.transformEventX, this.transformEventY)
            .scale(this.transformEventK)
        )

        if (elapsed > this.transitionDuration + 100) {
          setTimeout(() => {
            this.painting = false
          }, 500)

          t.stop()
          if (!this.hasFit) {
            this.fitViz()
            setTimeout(() => {
              this.loading = true
            }, 600)
          }
        }
      })
    },
    fitViz(node) {
      let x, y, k

      if (node) {
        let elem = this.custom
          .selectAll('circle')
          .filter(d => d.id == this.selectedTaskId)

        k = 1

        x = this.width / 2 - k * elem.attr('cx')
        y = this.height / 2 - k * elem.attr('cy')
      } else {
        let bounds = {
          width: this.canvasBbox.right + 50,
          height: this.canvasBbox.bottom + 50
        }

        k =
          0.7 / Math.max(bounds.width / this.width, bounds.height / this.height)

        x = this.width / 2 - k * (bounds.width / 2)
        y = this.height / 2 - k * (bounds.height / 2)
      }

      this.canvas
        .transition()
        .duration(500)
        .call(
          this.scaledZoom.transform,
          d3.zoomIdentity.translate(x, y).scale(k)
        )
    },
    drawCanvas(transform) {
      const context = this.context

      let bbox = this.canvasBbox

      context.clearRect(0, 0, this.width, this.height)

      let nodes = this.custom.selectAll('circle')
      nodes.each(function() {
        // context.beginPath()

        let node = d3.select(this)
        // context.fillStyle = node.attr('fill')

        let point = transform.apply([node.attr('cx'), node.attr('cy')])

        // context.arc(
        //   point[0],
        //   point[1],
        //   node.attr('r') * transform.k,
        //   0,
        //   2 * Math.PI
        // )
        // context.fill()
        if (point[0] > bbox.right) bbox.right = point[0]
        if (point[0] < bbox.left) bbox.left = point[0]
        if (point[1] > bbox.bottom) bbox.bottom = point[1]
        if (point[1] > bbox.top) bbox.top = point[1]
      })

      let edges = this.custom.selectAll('path')

      edges.each(function() {
        context.beginPath()

        let edge = d3.select(this)
        context.strokeStyle = edge.attr('stroke')
        context.lineCap = edge.attr('stroke-linecap')
        context.lineWidth = 5 * transform.k
        context.globalAlpha = edge.attr('stroke-opacity')

        edge.each(d => {
          let finalPoint,
            len = 1
          let _context
          d.data.points.forEach((p, i) => {
            let point = transform.apply([p.x, p.y])
            switch (i) {
              case 0:
                finalPoint = point
                context.moveTo(...point)
                break
              default:
                if (finalPoint) len = point[1] - finalPoint[1]
                finalPoint = point
                if (isDiagonal(_context[0], _context[1], point[0], point[1])) {
                  let to = makeQuadraticBezierPoints(
                    _context[0],
                    _context[1],
                    point[0],
                    point[1]
                  )
                  context.lineTo(...to[0])
                  context.lineTo(...to[1])
                }

                context.lineTo(point[0], point[1])
                break
            }

            _context = point
          })

          context.stroke()
          len
          let side = 25 * transform.k
          context.fillStyle = edge.attr('arrow-color')
          context.beginPath()
          context.moveTo(finalPoint[0], finalPoint[1] - 48 * transform.k)
          context.lineTo(
            finalPoint[0] - side,
            finalPoint[1] - 48 * transform.k - side
          )
          context.lineTo(
            finalPoint[0] + side,
            finalPoint[1] - 48 * transform.k - side
          )
          context.lineTo(finalPoint[0], finalPoint[1] - 48 * transform.k)
          context.fill()
        })
      })

      this.canvasBbox = bbox
    },
    labelNodes() {
      this.canvas.selectAll('text').remove()

      this.labels = this.globalGroup
        .append('g')
        .attr('id', 'labelGroup')
        .selectAll('text')
        .data(this.dag.descendants())
        .enter()
        .append('text')
        .text(d => d.data.name)
        .attr('text-anchor', 'middle')
        .attr('alignment-baseline', 'middle')
        .style('font-size', '0.55rem')
        .attr('display', this.showLabels ? 'block' : 'none')
        .attr('x', d => (d.x ? d.x : d.x1) + 10)
        .attr('y', d => (d.y ? d.y : d.y1) - 10)
    },
    updateNodes() {
      // Preserves references to this for event handlers
      const size = this.size * 2

      this.custom
        .selectAll('circle')
        .data(this.dag.descendants())
        .join(
          enter =>
            enter
              .append('circle')
              .attr('fill', d => {
                return this.selectedTaskId
                  ? this.selectedTaskId == d.id
                    ? this.calcNodeColor()
                    : this.calcColor(this.fadedNodeColor)
                  : this.calcNodeColor()
              })
              .attr('opacity', 0)
              .attr('cursor', 'pointer')
              .attr('cy', data =>
                data.y ? data.y : data.y0 + (data.y1 - data.y0) / 2
              )
              .call(enter =>
                enter
                  .transition()
                  .duration(this.transitionDuration)
                  .delay((d, i) => i * 10)
                  .attr('r', d =>
                    d.id == this.selectedTaskId ? size : size * 0.9
                  )
                  .attr('opacity', 1)
                  .attr('cx', data =>
                    data.x ? data.x : data.x0 + (data.x1 - data.x0) / 2
                  )
              ),
          update =>
            update
              .attr('fill', d => {
                return this.selectedTaskId
                  ? this.selectedTaskId == d.id
                    ? this.calcNodeColor()
                    : this.calcColor(this.fadedNodeColor)
                  : this.calcNodeColor()
              })
              .transition()
              .duration(this.transitionDuration)
              .delay((d, i) => i * 10)
              .attr('r', d => (d.id == this.selectedTaskId ? size : size * 0.9))
              .attr('cy', data =>
                data.y ? data.y : data.y0 + (data.y1 - data.y0) / 2
              )
              .attr('cx', data =>
                data.x ? data.x : data.x0 + (data.x1 - data.x0) / 2
              ),
          exit =>
            exit.call(exit =>
              exit
                .transition()
                .duration(this.transitionDuration)
                .remove()
            )
        )
    },
    updateEdges() {
      this.line = d3
        .line()
        .curve(d3[this.curve])
        .x(d => d.x)
        .y(d => d.y)

      this.custom
        .selectAll('path')
        .data(this.dag.links())
        .join(
          enter =>
            enter
              .append('path')
              .attr('stroke-linecap', 'round')
              .attr('fill', 'none')
              .attr('class', 'path')
              .attr('arrow-color', () => this.calcColor(this.defaultArrowColor))
              .attr('stroke-width', 4)
              .attr('stroke', this.calcStrokeColor)
              .call(enter => {
                enter
                  .transition()
                  .duration(this.transitionDuration)
                  .delay((d, i) => i * 10)
                  .attr('stroke-opacity', d => {
                    let opacity
                    if (this.selectedTaskId) {
                      if (
                        d.source.id == this.selectedTaskId ||
                        d.target.id == this.selectedTaskId
                      ) {
                        opacity = 1
                      } else {
                        opacity = 0.2
                      }
                    } else {
                      opacity = 1
                    }
                    return opacity
                  })
              }),
          update =>
            update
              .transition()
              .duration(this.transitionDuration)
              .delay((d, i) => i * 10)
              .attr('stroke', this.calcStrokeColor)
              .call(update => {
                update
                  .transition()
                  .duration(this.transitionDuration)
                  .delay((d, i) => i * 10)
                  .attr('stroke-opacity', d => {
                    let opacity
                    if (this.selectedTaskId) {
                      if (
                        d.source.id == this.selectedTaskId ||
                        d.target.id == this.selectedTaskId
                      ) {
                        opacity = 1
                      } else {
                        opacity = 0.2
                      }
                    } else {
                      opacity = 1
                    }
                    return opacity
                  })
              }),
          exit =>
            exit.call(exit =>
              exit
                .transition()
                .duration(this.transitionDuration)
                .remove()
            )
        )
    },
    getNodeFromTaskId(taskId) {
      return this.nodes.selectAll('g').filter(d => d.id == taskId)
    },
    handleSelect(task) {
      this.$emit('node-click', task)

      let taskId = task.id

      if (taskId !== this.selectedTaskId) {
        this.selectedTaskId = taskId

        this.fadeAllNodes()
        this.highlightNode(taskId)

        this.fadeAllEdges()
        this.highlightUpstreamEdges(taskId)
        this.highlightDownstreamEdges(taskId)

        this.$router.replace({
          query: { schematic: taskId }
        })
      } else {
        this.selectedTaskId = null

        this.showAllNodes()
        this.showAllEdges()

        this.$router.replace({
          query: { schematic: '' }
        })
      }
      let t = d3.timer(elapsed => {
        this.drawCanvas(this.transform)

        if (elapsed > this.transitionDuration) {
          t.stop()
        }
      })
    },
    showAllNodes() {
      this.custom
        .selectAll('circle')
        .transition()
        .duration(this.transitionDuration)
        .attr('fill', this.calcNodeColor)
    },
    showAllEdges() {
      this.custom
        .selectAll('path')
        .transition()
        .duration(this.transitionDuration)
        .attr('stroke', this.calcStrokeColor)
        .attr('stroke-opacity', 1)
    },
    fadeAllNodes() {
      this.custom
        .selectAll('circle')
        .transition()
        .duration(this.transitionDuration)
        .attr('fill', this.calcColor(this.fadedNodeColor))
    },
    fadeAllEdges() {
      this.custom
        .selectAll('path')
        .transition()
        .duration(this.transitionDuration)
        .attr('stroke-opacity', 0.2)
    },
    highlightNode(id) {
      this.custom
        .selectAll('circle')
        .filter(d => d.id == id)
        .transition()
        .duration(this.transitionDuration)
        .attr('fill', this.calcNodeColor)
    },
    highlightUpstreamEdges(id) {
      // Upstream edges
      this.custom
        .selectAll('path')
        .filter(({ source }) => source.id == id)
        .transition()
        .duration(this.transitionDuration)
        .attr('stroke-opacity', 1)
    },
    highlightDownstreamEdges(id) {
      // Downstream edges
      this.custom
        .selectAll('path')
        .filter(({ target }) => target.id == id)
        .transition()
        .duration(this.transitionDuration)
        .attr('stroke-opacity', 1)
    },
    calcStrokeColor(d) {
      if (d.target.data.state) {
        return STATE_COLORS[d.target.data.state]
      }
      return this.calcEdgeColor()
    },
    calcNodeColor() {
      let c = this.nodeColor || this.defaultNodeColor
      return `rgba(${c.r}, ${c.g}, ${c.b}, ${c.a})`
    },
    calcEdgeColor() {
      let c = this.edgeColor || this.defaultEdgeColor
      return `rgba(${c.r}, ${c.g}, ${c.b}, ${c.a})`
    },
    calcColor(c) {
      return `rgba(${c.r}, ${c.g}, ${c.b}, ${c.a})`
    },
    rgba2hex(orig) {
      let a,
        rgb = orig
          .replace(/\s/g, '')
          .match(/^rgba?\((\d+),(\d+),(\d+),?([^,\s)]+)?/i),
        alpha = ((rgb && rgb[4]) || '').trim(),
        hex = rgb
          ? (rgb[1] | (1 << 8)).toString(16).slice(1) +
            (rgb[2] | (1 << 8)).toString(16).slice(1) +
            (rgb[3] | (1 << 8)).toString(16).slice(1)
          : orig

      if (alpha !== '') {
        a = alpha
      } else {
        a = 1
      }
      // multiply before convert to HEX
      a = ((a * 255) | (1 << 8)).toString(16).slice(1)
      hex = hex + a

      return hex
    }
  }
}
</script>

<template>
  <div
    ref="container"
    class="position-relative full-height ma-0 pa-0"
    style="overflow: hidden;"
  >
    <v-card
      v-if="devToolbar"
      class="toolbox pa-0 d-flex align-center"
      :class="[
        showNodeColorSwatch || showEdgeColorSwatch ? 'swatch-open' : '',
        collapsed ? 'collapsed' : ''
      ]"
      tile
    >
      <v-row v-if="!collapsed" class="pa-0 mx-3">
        <v-col cols="12" class="pa-0">
          <v-row justify="center" align="center" class="pa-0">
            <v-col
              v-if="showNodeColorSwatch || showEdgeColorSwatch"
              key="1"
              cols="6"
              class="text-center overline"
            >
              <div>{{ showNodeColorSwatch ? 'Node' : 'Edge' }} color:</div>
              <v-color-picker
                v-model="color"
                light
                flat
                hide-canvas
                hide-mode-switch
                mode="rgba"
                :show-swatches="true"
                class="mx-auto"
                width="1000"
              ></v-color-picker>
            </v-col>
            <v-col
              key="2"
              :cols="showNodeColorSwatch || showEdgeColorSwatch ? 6 : 12"
            >
              <v-icon @click="collapsed = true">branding_watermark</v-icon>
              <v-btn class="my-3" text @click="fitViz(null)">
                <v-icon>border_outer</v-icon>
                <span>
                  Reset Viewport
                </span>
              </v-btn>

              <div
                class="color-picker py-2"
                :class="{ selected: showNodeColorSwatch }"
                @click="
                  showEdgeColorSwatch = false
                  showNodeColorSwatch = !showNodeColorSwatch
                "
              >
                <v-icon>arrow_left</v-icon>
                <span>
                  Node Color
                </span>
              </div>
              <div
                class="color-picker py-2"
                :class="{ selected: showEdgeColorSwatch }"
                @click="
                  showNodeColorSwatch = false
                  showEdgeColorSwatch = !showEdgeColorSwatch
                "
              >
                <v-icon>arrow_left</v-icon>
                <span>
                  Edge Color
                </span>
              </div>
              <v-checkbox
                v-model="showLabels"
                :disabled="!$route.params.id"
                label="Labels"
                @change="labelNodes"
              ></v-checkbox>
            </v-col>
          </v-row>
        </v-col>
      </v-row>
      <v-row v-else>
        <v-col cols="12" class="pa-0 text-center">
          <v-icon @click="collapsed = false">featured_video</v-icon>
        </v-col>
      </v-row>
    </v-card>

    <canvas :id="id" :style="canvasStyle" />

    <div
      v-if="showCards"
      class="node-data-group position-absolute"
      :style="nodeDataGroupTranslate"
    >
      <SchematicNode
        v-for="data in nodeData"
        :key="data.id"
        :k="transformEventK"
        :mapped="mappedTasks[data.id]"
        :node-data="data"
        :disabled="selectedTaskId && selectedTaskId !== data.id"
        @node-click="handleSelect"
      ></SchematicNode>
    </div>

    <v-toolbar v-if="!hideControls" dense class="toolbar px-0 mx-0">
      <v-tooltip top>
        <template v-slot:activator="{ on }">
          <v-btn icon tile v-on="on" @click="fitViz()">
            <v-icon>center_focus_strong</v-icon>
          </v-btn>
        </template>
        <span>
          Reset Viewport
        </span>
      </v-tooltip>

      <v-tooltip top>
        <template v-slot:activator="{ on }">
          <v-btn icon tile v-on="on" @click="_zoomIn">
            <v-icon>zoom_in</v-icon>
          </v-btn>
        </template>
        <span>
          Zoom In
        </span>
      </v-tooltip>

      <v-tooltip top>
        <template v-slot:activator="{ on }">
          <v-btn icon tile v-on="on" @click="_zoomOut">
            <v-icon>zoom_out</v-icon>
          </v-btn>
        </template>
        <span>
          Zoom Out
        </span>
      </v-tooltip>
    </v-toolbar>
  </div>
</template>

<style lang="scss">
// This block is has no style scoping,
// which allows us to use css
// to style dynamically attached svg elements
// .path {
// animation: dash 120s reverse linear;
// animation-iteration-count: infinite;
// stroke-dasharray: 5 7;
// }

@keyframes dash {
  to {
    stroke-dashoffset: 500;
  }
}
</style>

<style lang="scss" scoped>
canvas {
  cursor: grab;
  transition: opacity 500ms linear;
  user-select: none;

  &:active {
    cursor: grabbing;
  }
}

.position-absolute {
  position: absolute;
}

.position-relative {
  position: relative;
}

.node-data-group {
  height: 100%;
  left: 0;
  pointer-events: none;
  top: 0;
  transform-origin: 0 0;
  transition: opacity 500ms linear;
  width: 100%;
}

.toolbar {
  border-bottom-right-radius: 0 !important;
  bottom: 1rem;
  left: 1rem;
  position: absolute;
}
</style>

<style lang="scss" scoped>
.h-100 {
  height: calc(100% - 64px) !important;
  min-height: calc(100% - 64px) !important;
}

.toolbox {
  bottom: 1rem;
  height: 350px;
  overflow: hidden;
  position: absolute;
  right: 1rem;
  transform-origin: right;
  transition: all 500ms;
  width: 350px;

  &.swatch-open {
    width: 700px;
  }

  &.collapsed {
    height: 50px;
    width: 50px;
  }
}

.no-flows {
  left: 50%;
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
}

.color-picker {
  cursor: pointer;
  font-size: 1rem;
  line-height: 1rem;
  user-select: none;

  &.selected {
    background-color: rgba(0, 0, 0, 0.2);
  }
}
</style>
