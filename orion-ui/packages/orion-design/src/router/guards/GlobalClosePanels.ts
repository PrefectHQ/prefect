import { exitPanel } from '@prefecthq/miter-design'
import { RouteGuard } from '@/types/RouteGuard'

export class GlobalClosePanels implements RouteGuard {

  public before(): void {
    exitPanel()
  }

}