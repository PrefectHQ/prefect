import { RunHistory } from '@/models/RunHistory'
import { MockFunction } from '@/services/Mocker'

export const randomFlowRunHistory: MockFunction<RunHistory> = function(history?: Partial<RunHistory>) {
  return new RunHistory({
    intervalStart: history?.intervalStart ?? this.create('date'),
    intervalEnd: history?.intervalEnd ?? this.create('date'),
    // todo: Make this mock more realistic
    // mocking this with createMany produces pretty random data that doesn't follow business rules around states
    states: history?.states ?? this.createMany('flowRunStateHistory', this.create('number', [1, 5])),
  })
}