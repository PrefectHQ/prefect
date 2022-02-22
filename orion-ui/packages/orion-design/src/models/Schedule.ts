/* eslint-disable max-classes-per-file */
export type ISchedule = IRRuleSchedule | ICronSchedule | IIntervalSchedule
export type Schedule = RRuleSchedule | CronSchedule | IntervalSchedule

export type IRRuleSchedule = {
  timezone: string | null,
  rrule: string,
}

export type ICronSchedule = {
  timezone: string | null,
  cron: string,
  dayOr: boolean | null,
}

export type IIntervalSchedule = {
  timezone: string | null,
  interval: number,
  anchorDate: string | null,
}

export class RRuleSchedule implements IRRuleSchedule {
  public timezone: string | null
  public rrule: string

  public constructor(schedule: IRRuleSchedule) {
    this.timezone = schedule.timezone
    this.rrule = schedule.rrule
  }
}

export class CronSchedule implements ICronSchedule {
  public timezone: string | null
  public cron: string
  public dayOr: boolean | null

  public constructor(schedule: ICronSchedule) {
    this.timezone = schedule.timezone
    this.cron = schedule.cron
    this.dayOr = schedule.dayOr
  }
}

export class IntervalSchedule implements IIntervalSchedule {
  public timezone: string | null
  public interval: number
  public anchorDate: string | null

  public constructor(schedule: IIntervalSchedule) {
    this.timezone = schedule.timezone
    this.interval = schedule.interval
    this.anchorDate = schedule.anchorDate
  }
}