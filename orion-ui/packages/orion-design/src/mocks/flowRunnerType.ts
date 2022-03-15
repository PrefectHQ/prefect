import { MockFunction } from '@/services/Mocker'
import { FlowRunnerType } from '@/types/FlowRunnerType'

export const randomFlowRunnerType: MockFunction<FlowRunnerType> = function() {
  const flowRunnerTypes = ['universal', 'kubernetes', 'docker', 'subprocess'] as const

  return flowRunnerTypes[Math.floor(Math.random() * flowRunnerTypes.length)]
}