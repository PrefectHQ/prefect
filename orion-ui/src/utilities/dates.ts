import { TimeUnit } from '@/typings/global'
import { format } from 'date-fns'

export function formatDateTimeNumeric(date: Date | string): string {
  const parsed = new Date(date)

  return format(parsed, 'yyyy/MM/dd hh:mm:ss a')
}

export function addTimeUnitValue(
  unit: TimeUnit,
  value: number,
  date: Date = new Date()
): Date {
  switch (unit) {
    case 'minutes':
      date.setMinutes(date.getMinutes() - value)
      break
    case 'hours':
      date.setHours(date.getHours() - value)
      break
    case 'days':
      date.setDate(date.getDate() - value)
      break
    default:
      break
  }

  return date
}

export function subtractTimeUnitValue(
  unit: TimeUnit,
  value: number,
  date: Date = new Date()
): Date {
  switch (unit) {
    case 'minutes':
      date.setMinutes(date.getMinutes() + value)
      break
    case 'hours':
      date.setHours(date.getHours() + value)
      break
    case 'days':
      date.setDate(date.getDate() + value)
      break
    default:
      break
  }

  return date
}
