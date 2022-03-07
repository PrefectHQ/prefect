import { queue } from '@prefecthq/miter-design'
import { RouteGuard } from '@prefecthq/orion-design'

export class GlobalClosePanels implements RouteGuard {

  public before(): void {
    queue.splice(0)
  }

}