import { Deployment } from '@/models/Deployment'
import { MockFunction } from '@/services/Mocker'

export const randomDeployment: MockFunction<Deployment> = function(deployment?: Partial<Deployment>) {
  return {
    id: deployment?.id ?? this.create('string'),
    created: deployment?.created ?? this.create('date'),
    updated: deployment?.updated ?? this.create('date'),
    name: deployment?.name ?? this.create('string'),
    flowId: deployment?.flowId ?? this.create('string'),
    flowData: deployment?.flowData ?? {
      encoding: this.create('string'),
      blob: this.create('string'),
    },
    schedule: deployment?.schedule ?? null,
    isScheduleActive: deployment?.isScheduleActive ?? this.create('boolean'),
    parameters: deployment?.parameters ?? {},
    tags: deployment?.tags ?? this.createMany('string', 3),
    flowRunner: deployment?.flowRunner ?? null,
  }
}