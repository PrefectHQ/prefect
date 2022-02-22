export interface ISchedule {
  rrule?: string,
  cron?: string,
  dayOr?: boolean | null,
  interval?: number,
  anchorDate?: string | null,
  timezone: string | null,
}

export type IRRuleSchedule = Pick<ISchedule, 'rrule' | 'timezone'>
export type ICronSchedule = Pick<ISchedule, 'cron' | 'timezone' | 'dayOr'>
export type IIntervalSchedule = Pick<ISchedule, 'interval' | 'timezone' | 'anchorDate'>

export function isRRuleSchedule(schedule: ISchedule): schedule is IRRuleSchedule {
  return !!schedule.rrule
}

export function isCronSchedule(schedule: ISchedule): schedule is ICronSchedule {
  return !!schedule.cron
}

export function isIntervalSchedule(schedule: ISchedule): schedule is IIntervalSchedule {
  return !!schedule.interval
}

export class Schedule implements ISchedule {
  public timezone: string | null
  public rrule?: string
  public cron?: string
  public dayOr?: boolean | null
  public interval?: number
  public anchorDate?: string | null

  public constructor(schedule: ISchedule) {
    this.timezone = schedule.timezone

    if (isRRuleSchedule(schedule)) {
      this.rrule = schedule.rrule
    }

    if (isCronSchedule(schedule)) {
      this.cron = schedule.cron
      this.dayOr = schedule.dayOr
    }

    if (isIntervalSchedule(schedule)) {
      this.interval = schedule.interval
      this.anchorDate = schedule.anchorDate
    }
  }
}