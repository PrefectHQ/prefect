<template>
  <div ref="container">
    <svg :id="id" ref="chart" class="run-history-chart" />
  </div>
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import { ref } from 'vue'
import * as d3 from 'd3'

export interface Bucket {
  interval_start: Date
  interval_end: Date
  states: { [key: string]: number }
}

type SelectionType = d3.Selection<SVGGElement, unknown, HTMLElement, null>
type TransitionType = d3.TransitionLike<SVGRectElement, unknown>
type BarType = d3.Selection<SVGRectElement, unknown, HTMLElement, null>

class Props {
  data = prop<Bucket[]>({ required: true })
}

const suid = () => '_' + Math.random().toString(36).substr(2, 9)

@Options({})
export default class RunHistoryChart extends Vue.with(Props) {
  id: string = suid()

  height: number = 0
  width: number = 0

  xScale = d3.scaleTime()

  container = ref<HTMLElement>() as unknown as HTMLElement
  svg: SelectionType = null as unknown as d3.Selection<
    SVGGElement,
    unknown,
    HTMLElement,
    null
  >

  barSelection: SelectionType = null as unknown as d3.Selection<
    SVGGElement,
    unknown,
    HTMLElement,
    null
  >

  mounted(): void {
    this.handleWindowResize()
    window.addEventListener('resize', this.handleWindowResize)

    this.createScales()
    this.createChart()
  }

  handleWindowResize(): void {
    this.height = this.container.offsetHeight
    this.width = this.container.offsetWidth
  }

  createScales(): void {
    const start = this.data[0].interval_start
    const end = this.data[this.data.length - 1].interval_end
    this.xScale.domain([new Date(start), new Date(end)]).range([0, this.width])
  }

  createChart(): void {
    this.svg = d3.select('.run-history-chart')

    this.svg?.attr('viewbox', `0, 0, ${this.width}, ${this.height}`)

    this.barSelection = this.svg.append('g')

    this.updateBuckets()
  }

  updateBars(anchor: SelectionType): BarType | TransitionType | undefined {
    if (!this.barSelection) return
    return anchor
      .append('rect')
      .attr('width', this.width / this.data.length / 2 + 'px')
      .attr('height', (d) => {
        console.log(d)
        return '100px'
      })
  }

  updateBuckets(): void {
    if (!this.barSelection) return

    this.barSelection
      .selectAll('.bucket')
      .data(this.data)
      .join(
        (selection: any): any => {
          const g = selection.append('g')
          g.attr('id', (d: Bucket | any) => d.interval_start.toString()).style(
            'transform',
            (d) => {
              console.log(
                this.xScale(new Date(d.interval_start)),
                d.interval_start
              )
              return `translate(${this.xScale(new Date(d.interval_start))}px)`
            }
          )

          g.selectAll('rect')
            .data((d: Bucket) => Object.entries(d.states))
            .join(
              this.updateBars,
              () => {},
              () => {}
            )

          return g
        },
        // (selection: d3.Selection): SelectionType => {
        //   console.log(selection, typeof selection)
        //   const g = selection.append('g')

        //   // g.attr('id', (d: Bucket | any) => d.interval_start.toString())

        //   // g.selectAll('rect')
        //   //   .data((d: Bucket) => d.states)
        //   //   .join(this.updateBars)
        //   return g
        // },
        () => {},
        () => {}
      )
    //   .data(this.visibleLinks)
    //   .join(
    //     // enter
    //     (selection: any) =>
    //       selection
    //         .append('path')
    //         .attr('id', (d: Link) => d.source.id + '-' + d.target.id)
    //         .attr('class', (d: Link) =>
    //           this.useLinearGradient
    //             ? d.source.data.state == 'pending'
    //               ? d.source.data.state
    //               : null
    //             : d.source.data.state
    //         )
    //         .style('stroke', (d: Link, i: number) =>
    //           this.useLinearGradient
    //             ? `url("#${d.source.data.name + i}")`
    //             : null
    //         )
    //         .style('stroke-width', (d: Link) =>
    //           d.source.data.state == 'pending' ? 5 : 20
    //         )
    //         .attr('d', (d: Link) =>
    //           this.line([
    //             [d.source.cx, d.source.cy],
    //             [d.target.cx, d.target.cy]
    //           ])
    //         )
    //         .style('opacity', 1),
    //     // update
    //     (selection: any) =>
    //       selection
    //         .attr('id', (d: Link) => d.source.id + '-' + d.target.id)
    //         .attr('class', (d: Link) =>
    //           this.useLinearGradient
    //             ? d.source.data.state == 'pending'
    //               ? d.source.data.state
    //               : null
    //             : d.source.data.state
    //         )
    //         .style('stroke', (d: Link, i: number) =>
    //           this.useLinearGradient
    //             ? `url("#${d.source.data.name + i}")`
    //             : null
    //         )
    //         .style('stroke-width', (d: Link) =>
    //           d.source.data.state == 'pending' ? 5 : 20
    //         )
    //         .attr('d', (d: Link) =>
    //           this.line([
    //             [d.source.cx, d.source.cy],
    //             [d.target.cx, d.target.cy]
    //           ])
    //         )
    //         .style('opacity', 1),
    //     // exit
    //     (selection: any) => selection.remove()
    //   )
  }
}
</script>

<style lang="scss">
@use '@/styles/components/run-history--chart.scss';
</style>
