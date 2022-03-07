import { exitPanel } from '@prefecthq/miter-design'
import { RouteGuard } from '@prefecthq/orion-design'

export class GlobalClosePanels implements RouteGuard {

  public before(): void {
    exitPanel()
  }

}