<script>
import * as d3 from 'd3'
import uniqueId from 'lodash.uniqueid'

export default {
  props: {
    colors: { type: Array, default: () => null },
    segments: { type: Array, default: () => [] },
    width: { type: Number, default: () => null },
    height: { type: Number, default: () => null },
    outerRadius: { type: Number, default: () => null },
    innerRadius: { type: Number, default: () => null }
  },
  data() {
    return {
      id: uniqueId('ring'),
      pie: null,
      chart: null,
      arc: null,
      radius: null,
      total: 0
    }
  },
  watch: {
    segments: function() {
      this.refreshChart()
    }
  },
  mounted() {
    this.$nextTick(() => {
      this.createRingChart()
    })
  },
  updated() {
    this.$nextTick(() => {
      this.createRingChart()
    })
  },
  methods: {
    refreshChart() {
      this.clearChart()
      this.createRingChart()
    },
    clearChart() {
      d3.select(`#${this.id}`)
        .selectAll('*')
        .remove()
    },
    createRingChart() {
      this.width = this.width || 200
      this.height = this.height || 200
      this.radius = Math.min(this.width, this.height) / 2

      this.color = d3
        .scaleOrdinal()
        .range(this.colors || ['#fff', 'transparent'])

      this.arc = d3
        .arc()
        .outerRadius(this.outerRadius || this.radius * 0.95)
        .innerRadius(this.innerRadius || this.radius * 0.65)

      let totalArc = d3
        .arc()
        .outerRadius(this.outerRadius || this.radius * 0.95)
        .innerRadius(this.innerRadius || this.radius * 0.65)
        .startAngle(0)
        .endAngle(6.28319)

      this.pie = d3
        .pie()
        .sort(null)
        .value(d => {
          return d.value
        })

      this.chart = d3
        .select(`#${this.id}`)
        .attr('width', this.width)
        .attr('height', this.height)
        .append('g')
        .attr('transform', `translate(${this.width / 2}, ${this.height / 2})`)

      let total = this.chart.append('g').attr('class', 'arc-container')

      total
        .append('path')
        .attr('stroke', 'white')
        .attr('stroke-width', 0)
        .attr('class', 'arc-total')
        .attr('d', totalArc)
        .style('fill', 'rgba(255, 255, 255, 0.4)')

      this.updateRingChart()
    },
    updateRingChart() {
      this.chart.selectAll('.arc').exit()

      let category = this.chart
        .selectAll('.arc')
        .data(this.pie(this.segments))
        .enter()
        .append('g')
        .attr('class', 'arc-container')

      category
        .append('path')
        .attr('stroke', 'white')
        .attr('stroke-width', 0)
        .attr('class', 'arc')
        .style('fill', d => {
          return this.color(d.data.label)
        })

      category
        .select('.arc')
        .transition()
        .delay((d, i) => {
          return 1250 * i
        })
        .duration((d, i) => {
          // Multiplying i by 0
          // as a placeholder so that we keep the
          // total duration the same
          // Perhaps we can add this as a prop?
          return 2000 + i * 0
        })
        .attrTween('d', d => {
          let i = d3.interpolate(d.startAngle, d.endAngle)
          return t => {
            d.endAngle = i(t)
            return this.arc(d)
          }
        })
    }
  }
}
</script>

<template>
  <svg :id="id" />
</template>
