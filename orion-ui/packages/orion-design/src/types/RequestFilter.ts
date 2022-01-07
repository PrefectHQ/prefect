import { DeploymentFilter } from './DeploymentFilter'
import { FlowFilter } from './FlowFilter'
import { FlowRunFilter } from './FlowRunFilter'
import { TaskRunFilter } from './TaskRunFilter'

export interface RequestFilter {
  flows?: FlowFilter,
  flow_runs?: FlowRunFilter,
  task_runs?: TaskRunFilter,
  deployments?: DeploymentFilter,
}
