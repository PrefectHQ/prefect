export type IScheduleResponse = {
  rrule?: string,
  cron?: string,
  day_or?: boolean | null,
  interval?: number,
  anchor_date?: string | null,
  timezone: string | null,
}

export type IRRuleScheduleResponse = {
  rrule: string,
  timezone: string | null,
}

export type ICronScheduleResponse = {
  cron: string,
  timezone: string | null,
  day_or: boolean | null,
}

export type IIntervalScheduleResponse = {
  interval: number,
  timezone: string | null,
  anchor_date: string | null,
}