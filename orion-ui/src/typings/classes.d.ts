declare class D3Base {
  constructor()
  id: string
  height: number
  width: number

  container: HTMLElement
  svg: any

  padding: {
    top: number
    bottom: number
    middle: number
    left: number
    right: number
  }

  /**
   * A hook called after the component handles the window resize event
   */
  resize(): void

  private handleWindowResize(): void
  private initializeChartDimensions(): void

  mounted(): void
  destroyed(): void
}
