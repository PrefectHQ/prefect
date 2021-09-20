import { Vue, Options } from 'vue-class-component'
import { ref } from 'vue'

// Generates a semi-random id, useful for chart selectors
const suid = () => '_' + Math.random().toString(36).substr(2, 9)

type SelectionType = d3.Selection<SVGGElement, unknown, HTMLElement, null>

// declare class D3Base {
//   constructor()
//   id: string
//   height: number
//   width: number

//   container: HTMLElement
//   svg: SelectionType

//   padding: {
//     top: number
//     bottom: number
//     middle: number
//     left: number
//     right: number
//   }

//   /**
//    * A hook called after the component handles the window resize event
//    */
//   resize(): void

//   private handleWindowResize(): void
//   private initializeChartDimensions(): void

//   mounted(): void
//   destroyed(): void
// }

@Options({})
export class D3Base extends Vue {
  public id: string = suid()

  public height: number = 0
  public width: number = 0

  public container = ref<HTMLElement>() as unknown as HTMLElement
  public svg: SelectionType = null as unknown as d3.Selection<
    SVGGElement,
    unknown,
    HTMLElement,
    null
  >

  public padding: {
    top: number
    bottom: number
    middle: number
    left: number
    right: number
  } = {
    top: 12,
    bottom: 12,
    middle: 12,
    left: 16,
    right: 16
  }

  public paddingY = this.padding.top + this.padding.middle + this.padding.bottom
  public paddingX = this.padding.left + this.padding.right

  resize(): void {}

  private handleWindowResize(): void {
    if (!this.container)
      return window.removeEventListener('resize', this.handleWindowResize)

    this.height = this.container.offsetHeight
    this.width = this.container.offsetWidth

    if (this.svg) {
      this.svg.attr(
        'viewbox',
        `0, 0, ${this.width - this.paddingX}, ${this.height - this.paddingY}`
      )

      this.svg
        .select('rect')
        .attr(
          'height',
          `${
            this.height -
            this.padding.top -
            this.padding.bottom -
            this.padding.middle
          }px`
        )
    }

    this.resize()
  }

  private initializeChartDimensions(): void {
    if (!this.container)
      return window.removeEventListener('resize', this.handleWindowResize)

    this.height = this.container.offsetHeight
    this.width = this.container.offsetWidth

    if (this.svg) {
      this.svg.attr(
        'viewbox',
        `0, 0, ${this.width - this.paddingX}, ${this.height - this.paddingY}`
      )

      this.svg
        .select('rect')
        .attr(
          'height',
          `${
            this.height -
            this.padding.top -
            this.padding.bottom -
            this.padding.middle
          }px`
        )
    }
  }

  mounted(): void {
    this.initializeChartDimensions()
    window.addEventListener('resize', this.handleWindowResize)
  }

  destroyed() {
    window.removeEventListener('resize', this.handleWindowResize)
  }
}
