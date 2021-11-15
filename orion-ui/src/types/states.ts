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

export class StateSigns {
  public static readonly COMPLETED: StateDirection = 1
  public static readonly RUNNING: StateDirection = 1
  public static readonly SCHEDULED: StateDirection = 1
  public static readonly PENDING: StateDirection = 1
  public static readonly FAILED: StateDirection = -1
  public static readonly CANCELED: StateDirection = -1

  public static get(state: State): StateDirection {
    return this[state]
  }
}

export class StateIcons {
  public static readonly COMPLETED: StateIcon = 'pi-completed'
  public static readonly RUNNING: StateIcon = 'pi-running'
  public static readonly SCHEDULED: StateIcon = 'pi-scheduled'
  public static readonly PENDING: StateIcon = 'pi-pending'
  public static readonly FAILED: StateIcon = 'pi-failed'
  public static readonly CANCELED: StateIcon = 'pi-canceled'

  public static get(state: State): StateIcon {
    return this[state]
  }
}

export class StateColors {
  public static readonly COMPLETED: StateColor = 'var(--completed)'
  public static readonly RUNNING: StateColor = 'var(--running)'
  public static readonly SCHEDULED: StateColor = 'var(--scheduled)'
  public static readonly PENDING: StateColor = 'var(--pending)'
  public static readonly FAILED: StateColor = 'var(--failed)'
  public static readonly CANCELED: StateColor = 'var(--canceled)'

  public static get(state: State): StateColor {
    return this[state]
  }
}
