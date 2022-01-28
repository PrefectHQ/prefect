export const stateType = [
  'COMPLETED',
  'RUNNING',
  'SCHEDULED',
  'PENDING',
  'FAILED',
  'CANCELLED',
] as const

export type StateType = typeof stateType[number]