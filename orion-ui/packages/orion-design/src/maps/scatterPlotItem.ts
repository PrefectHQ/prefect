import { UiFlowRunHistory } from '@/models/UiFlowRunHistory'
import { MapFunction } from '@/services/Mapper'

type ScatterPlotItem = {
  id: string,
  x: Date,
  y: number,
  itemClass?: string,
}

export const mapUiFlowRunHistoryToScatterPlotItem: MapFunction<UiFlowRunHistory, ScatterPlotItem> = function(source: UiFlowRunHistory): ScatterPlotItem {
  return {
    id: source.id,
    x: source.timestamp,
    y: source.duration,
    itemClass: `scatter-plot-item--${source.stateType.toLowerCase()}`,
  }
}