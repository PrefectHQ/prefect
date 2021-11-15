export type State =
  | 'COMPLETED'
  | 'RUNNING'
  | 'SCHEDULED'
  | 'PENDING'
  | 'FAILED'
  | 'CANCELED'

export type StateDirection = 1 | -1
export type StateIcon = `pi-${Lowercase<State>}`
export type StateColor = `var(--${Lowercase<State>})`

export class States {
  public static readonly COMPLETED = 'COMPLETED'
  public static readonly RUNNING = 'RUNNING'
  public static readonly SCHEDULED = 'SCHEDULED'
  public static readonly PENDING = 'PENDING'
  public static readonly FAILED = 'FAILED'
  public static readonly CANCELED = 'CANCELED'
}

export const StateDirections: ReadonlyMap<State, StateDirection> = new Map([
  [States.COMPLETED, -1],
  [States.RUNNING, -1],
  [States.SCHEDULED, -1],
  [States.PENDING, -1],
  [States.FAILED, 1],
  [States.CANCELED, 1]
])

export const StateIcons: ReadonlyMap<State, StateIcon> = new Map([
  [States.COMPLETED, 'pi-completed'],
  [States.RUNNING, 'pi-running'],
  [States.SCHEDULED, 'pi-scheduled'],
  [States.PENDING, 'pi-pending'],
  [States.FAILED, 'pi-failed'],
  [States.CANCELED, 'pi-canceled']
])

export const StateColors: ReadonlyMap<State, StateColor> = new Map([
  [States.COMPLETED, 'var(--completed)'],
  [States.RUNNING, 'var(--running)'],
  [States.SCHEDULED, 'var(--scheduled)'],
  [States.PENDING, 'var(--pending)'],
  [States.FAILED, 'var(--failed)'],
  [States.CANCELED, 'var(--canceled)']
])
