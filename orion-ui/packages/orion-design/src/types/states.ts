import { stateType } from '@/models/StateType'

// duplicate of @/models/StateType
export type State = typeof stateType[number]

export type StateName =
  | 'Completed'
  | 'Running'
  | 'Scheduled'
  | 'Pending'
  | 'Failed'
  | 'Cancelled'

export type StateDirection = 1 | -1
export type StateIcon = `pi-${Lowercase<State>}`
export type StateColor = `var(--${Lowercase<State>})`

export const SubStates = ['Late', 'Crashed'] as const
export type SubState = typeof SubStates[number]

export class States {
  public static readonly COMPLETED = 'COMPLETED'
  public static readonly RUNNING = 'RUNNING'
  public static readonly SCHEDULED = 'SCHEDULED'
  public static readonly PENDING = 'PENDING'
  public static readonly FAILED = 'FAILED'
  public static readonly CANCELLED = 'CANCELLED'
}

export const StateNames: ReadonlyMap<State, StateName> = new Map([
  [States.COMPLETED, 'Completed'],
  [States.RUNNING, 'Running'],
  [States.SCHEDULED, 'Scheduled'],
  [States.PENDING, 'Pending'],
  [States.FAILED, 'Failed'],
  [States.CANCELLED, 'Cancelled'],
])

export const StateDirections: ReadonlyMap<State, StateDirection> = new Map([
  [States.COMPLETED, -1],
  [States.RUNNING, -1],
  [States.SCHEDULED, -1],
  [States.PENDING, -1],
  [States.FAILED, 1],
  [States.CANCELLED, 1],
])

export const StateIcons: ReadonlyMap<State, StateIcon> = new Map([
  [States.COMPLETED, 'pi-completed'],
  [States.RUNNING, 'pi-running'],
  [States.SCHEDULED, 'pi-scheduled'],
  [States.PENDING, 'pi-pending'],
  [States.FAILED, 'pi-failed'],
  [States.CANCELLED, 'pi-cancelled'],
])

export const StateColors: ReadonlyMap<State, StateColor> = new Map([
  [States.COMPLETED, 'var(--completed)'],
  [States.RUNNING, 'var(--running)'],
  [States.SCHEDULED, 'var(--scheduled)'],
  [States.PENDING, 'var(--pending)'],
  [States.FAILED, 'var(--failed)'],
  [States.CANCELLED, 'var(--cancelled)'],
])

export function isState(value: unknown): value is State {
  return Object.values(States).includes(value)
}

export function isSubState(value: unknown): value is SubState {
  return SubStates.includes(value as SubState)
}