<template>
  <div ref="container">
    <svg :id="id" ref="chart" class="run-history-chart" />
  </div>
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import { ref } from 'vue'
import * as d3 from 'd3'

const positiveStates: string[] = [
  'COMPLETED',
  'RUNNING',
  'SCHEDULED',
  'PENDING'
]
const mappedPositiveStates: [string, number][] = positiveStates.map(
  (d: string) => [d, +1]
)

const negativeStates: string[] = ['FAILED', 'CANCELLED']
const mappedNegativeStates: [string, number][] = negativeStates.map(
  (d: string) => [d, -1]
)

const directions: Map<string, number> = new Map([
  ...mappedPositiveStates,
  ...mappedNegativeStates
])

export interface StateAggregate {
  [key: string]: number
}

export interface Bucket {
  interval_start: Date
  interval_end: Date
  states: StateAggregate
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
  yScale = d3.scaleLinear()

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

  get buckets(): Bucket[] {
    return this.data.map((d: Bucket) => {
      const states: { [key: string]: number } = {}
      Object.entries(d.states).forEach(([state, count]) => {
        states[state] = count * (state == 'FAILED' ? -1 : 1)
      })
      return { ...d, states }
    })
  }

  get series(): any {
    return (
      d3
        .stack()
        .keys([...positiveStates.slice().reverse(), ...negativeStates])
        .value(
          /* @ts-ignore */
          (d, key: string) => (directions.get(key) || 1) * (d.states[key] || 0)
        )
        /* @ts-ignore */
        .offset(d3.stackOffsetDiverging)(this.data)
    )
  }

  get seriesMap(): Map<string, []> {
    return new Map(this.series.map((s: any) => [s.key, s]))
  }

  mounted(): void {
    this.handleWindowResize()
    window.addEventListener('resize', this.handleWindowResize)

    console.log(this.series)

    this.createChart()
    this.updateScales()
    this.updateBuckets()
  }

  updated(): void {
    this.updateBuckets()
  }

  handleWindowResize(): void {
    this.height = this.container.offsetHeight
    this.width = this.container.offsetWidth

    this.updateScales()
    this.updateBuckets()
  }

  updateScales(): void {
    const start = this.data[0].interval_start
    const end = this.data[this.data.length - 1].interval_end
    this.xScale.domain([new Date(start), new Date(end)]).range([0, this.width])

    console.log(this.series.flat(2), this.series)
    this.yScale
      .domain(
        // TODO: Figure out what the heck the overloads for D3 are supposed to be...
        /* @ts-ignore */
        // d3.extent(
        //   this.buckets
        //     .map((d) => d.states)
        //     .map((d) => Object.values(d))
        //     .flat()
        // )
        d3.extent(this.series.flat(2))
      )
      .rangeRound([0, this.height / 2])
  }

  createChart(): void {
    this.svg = d3.select('.run-history-chart')

    this.svg?.attr('viewbox', `0, 0, ${this.width}, ${this.height}`)

    this.barSelection = this.svg.append('g')

    // TODO: Remove this guidelines (for tesitng purposes only)
    this.svg
      .append('line')
      .attr('x1', 0)
      .attr('x2', this.width)
      .attr('y1', this.height / 2)
      .attr('y2', this.height / 2)
      .attr('stroke-width', 1)
      .attr('stroke', 'var(--inactive)')
  }

  updateBars(
    anchor: SelectionType,
    ...args: any
  ): BarType | TransitionType | undefined {
    if (!this.barSelection) return
    const maxWidth = this.width / this.data.length / 2

    return (
      anchor
        .append('rect')
        .attr('width', Math.min(6, maxWidth))
        // TODO: Figure out what the heck the overloads for D3 are supposed to be...
        /* @ts-ignore */
        .attr('height', ([state, count]: [string, number], i: number) => {
          console.log(i)
          const seriesSlot = this.seriesMap.get(state)?.[i]
          if (!seriesSlot) return 0

          return this.yScale(seriesSlot[1] - seriesSlot[0])
          // return this.height / 2 * arr?.reduce((curr, acc) => acc + curr[0], 0)
        })
        // TODO: Figure out what the heck the overloads for D3 are supposed to be...
        /* @ts-ignore */
        .attr('y', ([state, count]: [string, number], i: number) => {
          const seriesSlot = this.seriesMap.get(state)?.[i]
          if (!seriesSlot) return 0
          // if (state == 'FAILED') return this.height / 2
          // return 0
          return this.yScale(seriesSlot[0])
        })
        .attr(
          'class',
          // TODO: Figure out what the heck the overloads for D3 are supposed to be...
          /* @ts-ignore */
          ([state, count]: [string, number]) => state.toLowerCase() + '-fill'
        )
    )
  }

  updateBuckets(): void {
    if (!this.barSelection) return
    const maxWidth = this.width / this.data.length / 2

    // TODO: Figure out what the heck the overloads for D3 are supposed to be...
    /* @ts-ignore */
    this.barSelection
      .selectAll('.bucket')
      .data(this.data)
      .join('g')
      .attr('id', (d: Bucket | any) => d.interval_start.toString())
      .style(
        'transform',
        (d: Bucket) =>
          `translate(${
            this.xScale(new Date(d.interval_start)) +
            this.width / this.data.length / 4
          }px)`
      )
      // .join(
      //   // (selection: any) =>
      //   //   selection
      //   //     .append('g')
      //   //     // .attr('id', (d: Bucket | any) => d.interval_start.toString())
      //   //     .style(
      //   //       'transform',
      //   //       (d: Bucket) =>
      //   //         `translate(${
      //   //           this.xScale(new Date(d.interval_start)) +
      //   //           this.width / this.data.length / 4
      //   //         }px)`
      //   //     ),
      //   (selection: any) =>
      //     selection
      //       .attr('id', (d: Bucket | any) => d.interval_start.toString())
      //       .style(
      //         'transform',
      //         (d: Bucket) =>
      //           `translate(${
      //             this.xScale(new Date(d.interval_start)) +
      //             this.width / this.data.length / 4
      //           }px)`
      //       ),
      //   // (selection: d3.Selection): SelectionType => {
      //   //   console.log(selection, typeof selection)
      //   //   const g = selection.append('g')

      //   //   // g.attr('id', (d: Bucket | any) => d.interval_start.toString())

      //   //   // g.selectAll('rect')
      //   //   //   .data((d: Bucket) => d.states)
      //   //   //   .join(this.updateBars)
      //   //   return g
      //   // },
      //   () => {},
      //   () => {}
      // )
      .selectAll('rect')
      /* @ts-ignore */
      .data((d: Bucket, i: number) => {
        const arr = Object.entries(d.states).map(([state, count]) => {
          return { state: state, count: count, bucket_key: i }
        })
        return arr
      })
      .join('rect')
      .attr('width', Math.min(6, maxWidth))
      // TODO: Figure out what the heck the overloads for D3 are supposed to be...
      /* @ts-ignore */
      .attr('height', (d: any) => {
        const seriesSlot = this.seriesMap.get(d.state)?.[d.bucket_key]
        console.log(seriesSlot, d)
        if (!seriesSlot) return 0

        return seriesSlot[1] - seriesSlot[0]
      })
      // TODO: Figure out what the heck the overloads for D3 are supposed to be...
      /* @ts-ignore */
      .attr('y', (d: any) => {
        const seriesSlot = this.seriesMap.get(d.state)?.[d.bucket_key]
        if (!seriesSlot) return 0
        return seriesSlot[1]
      })
      .attr(
        'class',
        // TODO: Figure out what the heck the overloads for D3 are supposed to be...
        /* @ts-ignore */
        (d: any) => d.state.toLowerCase() + '-fill'
      )
    // /* @ts-ignore */
    // .join(
    //   this.updateBars,
    //   () => {},
    //   () => {}
    // )
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
