import { IScheduleResponse, isCronScheduleResponse, isIntervalScheduleResponse, isRRuleScheduleResponse } from '@/models/IScheduleResponse'
import { CronSchedule, IntervalSchedule, RRuleSchedule, Schedule } from '@/models/Schedule'
import { Profile } from '@/services/Translate'

export const scheduleProfile: Profile<IScheduleResponse, Schedule> = {
  toDestination(source) {
    if (isRRuleScheduleResponse(source)) {
      return new RRuleSchedule({
        timezone: source.timezone,
        rrule: source.rrule,
      })
    }

    if (isCronScheduleResponse(source)) {
      return new CronSchedule({
        timezone: source.timezone,
        cron: source.cron,
        dayOr: source.day_or,
      })
    }

    if (isIntervalScheduleResponse(source)) {
      return new IntervalSchedule({
        timezone: source.timezone,
        interval: source.interval,
        anchorDate: source.anchor_date,
      })
    }

    throw 'Invalid IScheduleResponse'
  },
  toSource(destination) {
    return {
      'timezone': destination.timezone,
      'rrule': (destination as RRuleSchedule).rrule,
      'cron': (destination as CronSchedule).cron,
      'day_or': (destination as CronSchedule).dayOr,
      'interval': (destination as IntervalSchedule).interval,
      'anchor_date': (destination as IntervalSchedule).anchorDate,
    }
  },
}