import { WorkspaceFeatureFlag } from '@prefecthq/prefect-ui-library'
import { MapFunction } from '@/services/mapper'
import { FlagResponse } from '@/types/flagResponse'
import { FeatureFlag } from '@/utilities/permissions'

export const mapFlagResponseToFeatureFlag: MapFunction<FlagResponse, FeatureFlag | WorkspaceFeatureFlag | null> = (source) => {
  switch (source) {
    case 'workers':
      return 'access:workers'
    case 'work_pools':
      return 'access:work_pools'
    case 'artifacts':
      return 'access:artifacts'
    case 'deployment_status':
      return 'access:deploymentStatus'
    case 'work_queue_status':
      return 'access:workQueueStatus'
    case 'flow_run_infra_overrides':
      return 'access:flowRunInfraOverrides'
    default:
      const exhaustiveCheck: never = source
      return null
  }
}