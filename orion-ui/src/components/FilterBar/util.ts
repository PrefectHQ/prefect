import { GlobalFilter, RunState, RunTimeFrame } from '@/typings/global'

export type FilterObject = {
  object: string
  label: string
  key: string
  icon?: string
}
type ValueOf<T> = T[keyof T]

const parseStateFilter = (
  object: string,
  key: string,
  states: RunState[]
): FilterObject[] => {
  const arr: FilterObject[] = []
  if (states.length == 6) {
    arr.push({
      object: object,
      label: 'All States',
      key: key,
      icon: 'pi-focus-3-line'
    })
  } else if (states.length > 0) {
    states.forEach((state) => {
      arr.push({
        object: object,
        label: state.name,
        key: key,
        icon: 'pi-focus-3-line'
      })
    })
  }
  return arr
}

const parseStringFilter = (
  object: string,
  key: string,
  values: string[]
): FilterObject[] => {
  const iconMap: { [key: string]: string } = {
    tags: 'pi-price-tag-3-line',
    ids: 'pi-search-line',
    names: 'pi-search-line'
  }
  return values.map<FilterObject>((value) => {
    return {
      object: object,
      label: value,
      key: key,
      icon: iconMap[key]
    }
  })
}

const parseTimeframeFilter = (
  object: string,
  key: string,
  timeframe: RunTimeFrame
): FilterObject[] => {
  const arr: FilterObject[] = []

  if (timeframe.from) {
    let filterValue
    if (timeframe.from.timestamp)
      filterValue = new Date(timeframe.from.timestamp).toLocaleString()
    else if (timeframe.from.value && timeframe.from.unit)
      filterValue = `${timeframe.from.value}${timeframe.from.unit.slice(0, 1)}`

    if (filterValue) {
      arr.push({
        object: object,
        label: `${
          timeframe.from.timestamp ? 'From: ' : 'Past '
        } ${filterValue}`,
        key: key,
        icon: 'pi-scheduled'
      })
    }
  }
  if (timeframe.to) {
    let filterValue
    if (timeframe.to.timestamp)
      filterValue = new Date(timeframe.to.timestamp).toLocaleString()
    else if (timeframe.to.value && timeframe.to.unit)
      filterValue = `${timeframe.to.value}${timeframe.to.unit.slice(0, 1)}`

    if (filterValue) {
      arr.push({
        object: object,
        label: `${timeframe.to.timestamp ? 'To: ' : 'Next '} ${filterValue}`,
        key: key,
        icon: 'pi-scheduled'
      })
    }
  }

  return arr
}

export const parseFilters = (gf: GlobalFilter): FilterObject[] => {
  let arr: FilterObject[] = []
  const objects = Object.entries(gf)
  objects.forEach(([object, f]: [string, ValueOf<GlobalFilter>]) => {
    const filters = Object.entries(f)

    filters.forEach(([filter, value]) => {
      let parsed: FilterObject[]

      switch (filter) {
        case 'states':
          parsed = parseStateFilter(object, filter, value as RunState[])
          break
        case 'timeframe':
          parsed = parseTimeframeFilter(object, filter, value as RunTimeFrame)
          break
        case 'tags':
        case 'ids':
        case 'names':
          parsed = parseStringFilter(object, filter, value as string[])
          break
        default:
          parsed = []
          break
      }

      arr = [...arr, ...parsed]
    })
  })

  return arr
}
