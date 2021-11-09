import { format } from 'date-fns'

export function timeZoneAbbreviation(date: Date | string): string {
  const parsed = new Date(date)

  return parsed
    .toLocaleTimeString(undefined, { timeZoneName: 'short' })
    .split(' ')[2]
}

export function formatDateTimeNumeric(date: Date | string): string {
  const parsed = new Date(date)
  const dateTime = format(parsed, 'MM/dd/yyyy hh:mm:ss a')
  const timezone = timeZoneAbbreviation(parsed)

  return `${dateTime} ${timezone}`
}
