import { TimeFrame } from '@/typings/global'
import { addTimeUnitValue, subtractTimeUnitValue } from '@/utilities/dates'

function isValidTimeFrame(
  timeFrame: TimeFrame | undefined
): timeFrame is TimeFrame {
  return (
    timeFrame?.timestamp !== undefined ||
    (timeFrame?.value !== undefined && timeFrame.unit !== undefined)
  )
}

function calculateStart(timeFrame: TimeFrame): Date | null {
  if (timeFrame.timestamp) {
    return timeFrame.timestamp
  }

  if (timeFrame.unit && timeFrame.value) {
    return subtractTimeUnitValue(timeFrame.unit, timeFrame.value)
  }

  return null
}

function calculateEnd(timeFrame: TimeFrame): Date | null {
  if (timeFrame.timestamp) {
    return timeFrame.timestamp
  }

  if (timeFrame.unit && timeFrame.value) {
    return addTimeUnitValue(timeFrame.unit, timeFrame.value)
  }

  return null
}

export { isValidTimeFrame, calculateStart, calculateEnd }
