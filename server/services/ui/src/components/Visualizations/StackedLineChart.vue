<script>
import * as d3 from 'd3'
import uniqueId from 'lodash.uniqueid'

export default {
  props: {
    colors: { type: Object, default: () => {} },
    height: { type: Number, default: () => null },
    segments: { type: Array, default: () => [] },
    vertical: { type: Boolean, default: () => false },
    width: { type: Number, default: () => null }
  },
  data() {
    return {
      id: uniqueId('stackedLine'),
      chart: null,
      sum: 0,
      xShift: 0,
      yShift: 0
    }
  },
  computed: {
    paddingBottom() {
      return 100 * (this.height / this.width) + '%'
    },
    filteredSegments() {
      return this.segments.filter(s => s.value > 0)
    }
  },
  watch: {
    segments: {
      deep: true,
      handler() {
        if (!this.chart) this.createChart()
        setTimeout(() => {
          this.updateChart()
        }, 50)
      }
    }
  },
  mounted() {
    this.createChart()
    setTimeout(() => {
      this.updateChart()
    }, 50)
  },
  updated() {
    if (!this.chart) this.createChart()
    setTimeout(() => {
      this.updateChart()
    }, 50)
  },
  beforeDestroy() {
    window.onresize = null
  },
  methods: {
    calcHeight(d, i) {
      if (!this.vertical || (this.sum === 0 && i === 0)) return this.chartHeight
      if (this.sum === 0) return 0
      return this.scale(d.value)
    },
    calcWidth(d, i) {
      if (this.vertical || (this.sum === 0 && i === 0)) return this.chartWidth
      if (this.sum === 0) return 0
      return this.scale(d.value)
    },
    calcX(d) {
      if (this.vertical) return 0
      let x = this.xShift
      this.xShift += this.scale(d.value)
      return x
    },
    calcY(d) {
      if (!this.vertical) return 0
      let y = this.yShift
      this.yShift += this.scale(d.value)
      return y
    },
    createChart() {
      this.chart = d3.select(`#${this.id}`)
      window.onresize = this.updateChart
    },
    statusStyle(state) {
      return {
        'border-radius': '50%',
        display: 'inline-block',
        'background-color': this.colors[state],
        height: '1rem',
        width: '1rem'
      }
    },
    updateChart() {
      let parent = this.chart.select(function() {
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
          computedStyle.getPropertyValue('padding-bottom')
        )

      this.chartWidth = this.vertical
        ? this.width
        : parent._groups[0][0].clientWidth - paddingLeft - paddingRight

      this.chartHeight = this.vertical
        ? parent._groups[0][0].clientHeight - paddingTop - paddingBottom
        : this.height

      if (
        !this.chartHeight ||
        !this.chartWidth ||
        this.chartHeight < 0 ||
        this.chartWidth < 0
      ) {
        return
      }

      this.chart
        .attr('viewbox', `0 0 ${this.chartWidth} ${this.chartHeight}`)
        .attr('width', this.chartWidth)
        .attr('height', this.chartHeight)

      this.sum = d3.sum(this.segments, d => +d.value)

      this.scale = d3
        .scaleLinear()
        .range([0, this.vertical ? this.chartHeight : this.chartWidth])
        .domain([0, this.sum])

      this.xShift = 0
      this.yShift = 0

      this.chart
        .selectAll('.rect')
        .data(this.segments)
        .join(
          enter =>
            enter
              .append('rect')
              .attr('stroke', 'white')
              .attr('stroke-width', this.filteredSegments > 1 ? 1 : 0)
              .attr('class', 'rect')
              .attr('id', d => d.label)
              .style('fill', (d, i) => {
                if (this.sum === 0 && i === 0) return '#efefef'
                if (this.sum === 0) return 'transparent'
                return this.colors[d.label]
              })
              .attr('height', (d, i) =>
                this.vertical ? 0 : this.calcHeight(d, i)
              )
              .attr('width', (d, i) =>
                !this.vertical ? 0 : this.calcWidth(d, i)
              )
              .attr('y', () =>
                this.vertical ? this.chartHeight - this.yShift : null
              )
              .call(enter =>
                enter
                  .transition()
                  .duration(500)
                  .attr('height', (d, i) => this.calcHeight(d, i))
                  .attr('width', (d, i) => this.calcWidth(d, i))
                  .attr('x', d => this.calcX(d))
                  .attr('y', d => this.calcY(d))
              ),
          update =>
            update.call(update =>
              update
                .transition()
                .duration(500)
                .style('fill', (d, i) => {
                  if (this.sum === 0 && i === 0) return '#efefef'
                  if (this.sum === 0) return 'transparent'
                  return this.colors[d.label]
                })
                .attr('height', (d, i) => this.calcHeight(d, i))
                .attr('width', (d, i) => this.calcWidth(d, i))
                .attr('x', d => this.calcX(d))
                .attr('y', d => this.calcY(d))
            ),
          exit =>
            exit.call(exit =>
              exit
                .transition()
                .duration(500)
                .remove()
            )
        )
    }
  }
}
</script>

<template>
  <v-tooltip :bottom="!vertical" :right="vertical">
    <template v-slot:activator="{ on }">
      <svg :id="id" preserveAspectRatio="xMinYMin meet" v-on="on" />
    </template>
    <div v-if="filteredSegments.length > 0">
      <div
        v-for="segment in filteredSegments"
        :key="segment.label"
        class="svg-tooltip"
      >
        <span :style="statusStyle(segment.label)"></span>
        <span>{{ segment.label }}: {{ segment.value.toLocaleString() }}</span>
      </div>
    </div>
    <div v-else>
      No data.
    </div>
  </v-tooltip>
</template>

<style lang="scss" scoped>
.svg-tooltip {
  align-items: center;
  display: flex;

  span {
    margin: 0 5px;
  }
}
</style>
