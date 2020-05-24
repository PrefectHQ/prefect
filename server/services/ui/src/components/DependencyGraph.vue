<script>
import { select, event } from 'd3-selection'
import { zoom } from 'd3-zoom'
import dagreD3 from 'dagre-d3'

export default {
  props: {
    nodes: {
      required: true,
      type: Array,
      validator: nodes => (nodes.length ? nodes[0].id && nodes[0].label : true)
    },
    edges: {
      required: true,
      type: Array,
      validator: edges =>
        edges.length ? edges[0].fromId && edges[0].toId : true
    },
    mainTaskName: {
      required: true,
      type: String
    }
  },
  data() {
    return {
      graph: null,
      renderer: new dagreD3.render(),
      height: 200,
      viewBox: null,
      width: 411
    }
  },
  watch: {
    nodes() {
      this.render()
    },
    edges() {
      this.render()
    },
    mainTaskName() {
      this.render()
    }
  },
  mounted() {
    this.render()
  },
  methods: {
    calculateHeightAndWidth(height, width) {
      this.viewBox = `0 0 ${width} ${height}`
    },
    createChart() {
      select('#dependency-graph-svg')
        .selectAll('g')
        .remove()

      // Create the input graph
      this.graph = new dagreD3.graphlib.Graph()
        .setGraph({})
        .setDefaultEdgeLabel(function() {
          return {}
        })
    },
    render() {
      this.createChart()
      this.setNodes()
      this.setEdges()

      // Set up an SVG group so that we can translate the final graph.
      const svg = select('#dependency-graph-svg')

      const svgGroup = svg.append('g')

      const graphZoom = zoom().on('zoom', function() {
        svgGroup.attr('transform', event.transform)
      })

      this.graph.graph().marginx = 40
      this.graph.graph().marginy = 40

      this.graph.graph().transition = function(selection) {
        return selection.transition().duration(500)
      }

      svg.call(graphZoom)
      // Run the renderer. This is what draws the final graph.
      this.renderer(svgGroup, this.graph)

      const { height, width } = this.graph.graph()
      this.calculateHeightAndWidth(height, width)
    },
    setNodes() {
      this.nodes.forEach(node => {
        let nodeClass = `${node.label}`

        if (node.main) {
          nodeClass += ' main-task'
        } else {
          nodeClass += ' '
        }
        if (node.state) {
          nodeClass += `--${node.state}`
        }

        this.graph.setNode(node.id, {
          label: node.label,
          class: nodeClass
        })
      })

      this.graph.nodes().forEach(identifier => {
        let node = this.graph.node(identifier)
        // Round the corners of the nodes
        node.rx = node.ry = 5
      })
    },
    setEdges() {
      this.edges.forEach(edge => {
        this.graph.setEdge(edge.fromId, edge.toId)
      })
    }
  }
}
</script>

<template>
  <v-layout id="dependency-graph" class=" py-2" align-center justify-center>
    <div>
      <svg
        id="dependency-graph-svg"
        class="dependency-graph"
        xmlns="http://www.w3.org/2000/svg"
        :height="height"
        :viewBox="viewBox"
        :width="width"
      />
    </div>
  </v-layout>
</template>

<style lang="scss">
.dependency-graph {
  cursor: grab;
  user-select: none;

  &:active {
    cursor: grabbing;
  }

  rect {
    fill: #fff;
    stroke: var(--v-secondary-base);
    stroke-width: 1.5px;
  }

  path {
    stroke: var(--v-secondary-base);
    stroke-width: 1.5px;
  }

  .main-task {
    rect {
      fill: var(--v-secondary-base);
    }

    .label {
      fill: #fff;
    }

    &--Pending {
      rect {
        fill: var(--v-Pending-base);
        stroke: var(--v-Pending-base);
      }

      .label {
        fill: #fff;
      }
    }

    &--Scheduled {
      rect {
        fill: var(--v-Scheduled-base);
        stroke: var(--v-Scheduled-base);
      }

      .label {
        fill: #fff;
      }
    }

    &--Retrying {
      rect {
        fill: var(--v-Retrying-base);
        stroke: var(--v-Retrying-base);
      }

      .label {
        fill: #fff;
      }
    }

    &--Resuming {
      rect {
        fill: var(--v-Resuming-base);
        stroke: var(--v-Resuming-base);
      }

      .label {
        fill: #fff;
      }
    }

    &--Queued {
      rect {
        fill: var(--v-Queued-base);
        stroke: var(--v-Queued-base);
      }

      .label {
        fill: #fff;
      }
    }

    &--Submitted {
      rect {
        fill: var(--v-Submitted-base);
        stroke: var(--v-Submitted-base);
      }

      .label {
        fill: #fff;
      }
    }

    &--Paused {
      rect {
        fill: var(--v-Paused-base);
        stroke: var(--v-Paused-base);
      }

      .label {
        fill: #fff;
      }
    }

    &--Running {
      rect {
        fill: var(--v-Running-base);
        stroke: var(--v-Running-base);
      }

      .label {
        fill: #fff;
      }
    }

    &--Listening {
      rect {
        fill: var(--v-Listening-base);
      }
    }

    &--Finished {
      rect {
        fill: var(--v-Finished-base);
        stroke: var(--v-Finished-base);
      }

      .label {
        fill: #fff;
      }
    }

    &--Success {
      rect {
        fill: var(--v-Success-base);
        stroke: var(--v-Success-base);
      }

      .label {
        fill: #fff;
      }
    }

    &--Failed {
      rect {
        fill: var(--v-Failed-base);
        stroke: var(--v-Failed-base);
      }

      .label {
        fill: #fff;
      }
    }

    &--Cancelled {
      rect {
        fill: var(--v-Cancelled-base);
        stroke: var(--v-Cancelled-base);
      }

      .label {
        fill: #fff;
      }
    }

    &--Cached {
      rect {
        fill: var(--v-Cached-base);
        stroke: var(--v-Cached-base);
      }

      .label {
        fill: #fff;
      }
    }

    &--TriggerFailed {
      rect {
        fill: var(--v-TriggerFailed-base);
        stroke: var(--v-TriggerFailed-base);
      }

      .label {
        fill: #fff;
      }
    }

    &--Skipped {
      rect {
        fill: var(--v-Skipped-base);
        stroke: var(--v-Skipped-base);
      }

      .label {
        fill: #fff;
      }
    }

    &--TimedOut {
      rect {
        fill: var(--v-TimedOut-base);
        stroke: var(--v-TimedOut-base);
      }

      .label {
        fill: #fff;
      }
    }

    &--Mapped {
      rect {
        fill: var(--v-Mapped-base);
        stroke: var(--v-Mapped-base);
      }

      .label {
        fill: #fff;
      }
    }
  }
  // State color classes
  /* stylelint-disable  */
  .--Pending {
    rect {
      stroke: var(--v-Pending-base);
    }
  }

  .--Scheduled {
    rect {
      stroke: var(--v-Scheduled-base);
    }
  }

  .--Retrying {
    rect {
      stroke: var(--v-Retrying-base);
    }
  }

  .--Resuming {
    rect {
      stroke: var(--v-Resuming-base);
    }
  }

  .--Queued {
    rect {
      stroke: var(--v-Queued-base);
    }
  }

  .--Submitted {
    rect {
      stroke: var(--v-Submitted-base);
    }
  }

  .--Paused {
    rect {
      stroke: var(--v-Paused-base);
    }
  }

  .--Running {
    rect {
      stroke: var(--v-Running-base);
    }
  }

  .--Listening {
    rect {
      stroke: var(--v-Listening-base);
    }
  }

  .--Finished {
    rect {
      stroke: var(--v-Finished-base);
    }
  }

  .--Success {
    rect {
      stroke: var(--v-Success-base);
    }
  }

  .--Failed {
    rect {
      stroke: var(--v-Failed-base);
    }
  }

  .--Cancelled {
    rect {
      stroke: var(--v-Cancelled-base);
    }
  }

  .--Cached {
    rect {
      stroke: var(--v-Cached-base);
    }
  }

  .--TriggerFailed {
    rect {
      stroke: var(--v-TriggerFailed-base);
    }
  }

  .--Skipped {
    rect {
      stroke: var(--v-Skipped-base);
    }
  }

  .--TimedOut {
    rect {
      stroke: var(--v-TimedOut-base);
    }
  }

  .--Mapped {
    rect {
      stroke: var(--v-Mapped-base);
    }
  }
  /* stylelint-enable  */
}
</style>
