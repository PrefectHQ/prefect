# Schedules

Schedules tell the Orion server how to automatically create new flow runs on a specified cadence.

Users can add a schedule to any [deployment](/concepts/deployments/). The Orion `Scheduler` service will periodically visit every deployment and create new flow runs according to its schedule. In addition to the `Scheduler` service, auto-scheduled runs are proactively generated any time a deployment is created or modified.

## Types of Schedules

Prefect supports three different types of schedules that cover a wide range of use cases and offer a large degree of customization:

- The `IntervalSchedule` is best suited for deployments that need to run at some consistent cadence that isn't related to absolute time
- The `RRuleSchedule` is best suited for deployments that rely on calendar logic for simple recurrance, irregular intervals, exclusions or day-of-month adjustments
- The `CronSchedule` is most appropriate for users who are already familiar with `cron` from use in other systems

### IntervalSchedule

(For more detail, please see the [`IntervalSchedule` API reference][prefect.orion.schemas.schedules.intervalschedule].)

An `IntervalSchedule` creates new flow runs on a regular interval measured in seconds. Intervals are computed from an `anchor_date` that defaults to January 1, 2020 at midnight UTC. Users can also specify a `timezone`.

!!! info "Daylight saving time considerations"
    If the schedule's `anchor_date` or `timezone` are provided with a DST-observing timezone, then the schedule will adjust itself appropriately. Intervals greater than 24 hours will follow DST conventions, while intervals of less than 24 hours will follow UTC intervals. For example, an hourly schedule will fire every UTC hour, even across DST boundaries. When clocks are set back, this will result in two runs that _appear_ to both be scheduled for 1am local time, even though they are an hour apart in UTC time. For longer intervals, like a daily schedule, the interval schedule will adjust for DST boundaries so that the clock-hour remains constant. This means that a daily schedule that always fires at 9am will observe DST and continue to fire at 9am in the local time zone.

### RRulesSchedule

(For more detail, please see the [`RRulesSchedule` API reference][prefect.orion.schemas.schedules.rrulesschedule].)

An `RRulesSchedule` creates calendar-based recurrances that are compatible with the iCalendar (`.ics`) standard ([RFC 5545](https://datatracker.ietf.org/doc/html/rfc5545)) as implemented by `dateutils.rrule`.

RRules are appropriate for any kind of calendar-date manipulation, including simple repetition, irregular intervals, exclusions, week day or day-of-month adjustments, and more. RRules can represent complex logic like: - The last weekday of each month - The fourth Thursday of November - Every other day of the week - etc.

!!! info "Daylight saving time considerations"
    Note that as a calendar-oriented standard, `RRuleSchedules` are sensitive to to the initial timezone provided. A 9am daily schedule with a daylight saving time-aware start date will maintain a local 9am time through DST boundaries; a 9am daily schedule with a UTC start date will maintain a 9am UTC time.

### CronSchedule

(For more detail, please see the [`CronSchedule` API reference][prefect.orion.schemas.schedules.cronschedule].)

A `CronSchedule` creates new flow runs according to a provided [cron](https://en.wikipedia.org/wiki/Cron) string. Users may also provide a timezone to enforce DST behaviors.

!!! info "Daylight saving time considerations"
    If the timezone is a DST-observing one, then the schedule will adjust itself appropriately. Cron's rules for DST are based on schedule times, not intervals. This means that an hourly cron schedule will fire on every new schedule hour, not every elapsed hour; for example, when clocks are set back this will result in a two-hour pause as the schedule will fire _the first time_ 1am is reached and _the first time_ 2am is reached, 120 minutes later. Longer schedules, such as one that fires at 9am every morning, will automatically adjust for DST.

## The Scheduler service

The `Scheduler` service is started automatically when `prefect orion start` is run. By default, it visits deployments on a [60-second loop][prefect.utilities.settings.servicessettings.scheduler_loop_seconds] and attempts to create up to [100][prefect.utilities.settings.servicessettings.scheduler_max_runs] scheduled flow runs up to [100 days][prefect.utilities.settings.servicessettings.scheduler_max_scheduled_time] in the future. This means that if a deployment has an hourly schedule, the default settings will create runs for the next 4 days (or 100 hours). If it has a weekly schedule, the default settings will maintain the next 14 runs (up to 100 days in the future).

!!! info "The scheduler does not affect execution"
    The Orion `Scheduler` service only creates new flow runs and places them in `Scheduled` states; it is not at all involved in flow or task execution. Making the scheduler loop faster will not make flows start or run faster.

!!! tip "Additional Reading"
    To learn more about the concepts presented here, check out the following resources:

    - [Deployments](/api-ref/prefect/deployments/)
