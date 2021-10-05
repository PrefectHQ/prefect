import { Vue, Options } from 'vue-class-component'
import { ref } from 'vue'

// Generates a semi-random id, useful for chart selectors
const suid = () => '_' + Math.random().toString(36).substr(2, 9)

type SelectionType = d3.Selection<SVGGElement, unknown, HTMLElement, null>

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
    top: 0,
    bottom: 0,
    middle: 0,
    left: 0,
    right: 0
  }

  public get paddingY(): number {
    return this.padding.top + this.padding.middle + this.padding.bottom
  }

  public get paddingX(): number {
    return this.padding.left + this.padding.right
  }

  resize(): void {
    return
  }

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
    }
  }

  mounted(): void {
    requestAnimationFrame(() => {
      this.initializeChartDimensions()
    })
    window.addEventListener('resize', this.handleWindowResize)
  }

  destroyed(): void {
    window.removeEventListener('resize', this.handleWindowResize)
  }
}
