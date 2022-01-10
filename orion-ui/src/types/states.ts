export type StateType =
  | 'COMPLETED'
  | 'RUNNING'
  | 'SCHEDULED'
  | 'PENDING'
  | 'FAILED'
  | 'CANCELLED'

export type StateName =
  | 'Completed'
  | 'Running'
  | 'Scheduled'
  | 'Pending'
  | 'Failed'
  | 'Cancelled'

export type StateDirection = 1 | -1
export type StateIcon = `pi-${Lowercase<StateType>}`
export type StateColor = `var(--${Lowercase<StateType>})`

export class States {
  public static readonly COMPLETED = 'COMPLETED'
  public static readonly RUNNING = 'RUNNING'
  public static readonly SCHEDULED = 'SCHEDULED'
  public static readonly PENDING = 'PENDING'
  public static readonly FAILED = 'FAILED'
  public static readonly CANCELLED = 'CANCELLED'
}

export const StateNames: ReadonlyMap<StateType, StateName> = new Map([
  [States.COMPLETED, 'Completed'],
  [States.RUNNING, 'Running'],
  [States.SCHEDULED, 'Scheduled'],
  [States.PENDING, 'Pending'],
  [States.FAILED, 'Failed'],
  [States.CANCELLED, 'Cancelled']
])

export const StateDirections: ReadonlyMap<StateType, StateDirection> = new Map([
  [States.COMPLETED, -1],
  [States.RUNNING, -1],
  [States.SCHEDULED, -1],
  [States.PENDING, -1],
  [States.FAILED, 1],
  [States.CANCELLED, 1]
])

export const StateIcons: ReadonlyMap<StateType, StateIcon> = new Map([
  [States.COMPLETED, 'pi-completed'],
  [States.RUNNING, 'pi-running'],
  [States.SCHEDULED, 'pi-scheduled'],
  [States.PENDING, 'pi-pending'],
  [States.FAILED, 'pi-failed'],
  [States.CANCELLED, 'pi-cancelled']
])

export const StateColors: ReadonlyMap<StateType, StateColor> = new Map([
  [States.COMPLETED, 'var(--completed)'],
  [States.RUNNING, 'var(--running)'],
  [States.SCHEDULED, 'var(--scheduled)'],
  [States.PENDING, 'var(--pending)'],
  [States.FAILED, 'var(--failed)'],
  [States.CANCELLED, 'var(--cancelled)']
])
