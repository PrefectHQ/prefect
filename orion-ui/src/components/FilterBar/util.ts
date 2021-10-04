import { GlobalFilter } from '@/typings/global'

export type FilterObject = {
  objectKey: string
  objectLabel: string
  filterKey: string
  filterValue: any
  icon: string
}

export const parseFilters = (gf: GlobalFilter) => {
  const arr: FilterObject[] = []
  const keys = Object.keys(gf)
  keys.forEach((key) => {
    Object.entries(gf[key as keyof GlobalFilter]).forEach(
      ([k, v]: [string, any]) => {
        if (k == 'states' && Array.isArray(v)) {
          let filterValue

          if (v.length == 6) filterValue = 'All'
          else if (v.length == 0) filterValue = 'None'
          else filterValue = v.join(', ')

          arr.push({
            objectKey: key,
            objectLabel: v.length == 1 ? 'State' : 'States',
            filterKey: k,
            filterValue: filterValue,
            icon: 'pi-focus-3-line'
          })
        } else if (k == 'timeframe') {
          if (v.from) {
            let filterValue
            if (v.from.timestamp)
              filterValue = new Date(v.from.timestamp).toLocaleString()
            else if (v.from.value && v.from.unit)
              filterValue = `${v.from.value}${v.from.unit.slice(0, 1)}`

            arr.push({
              objectKey: key,
              objectLabel: `Past ${filterValue}`,
              filterKey: k,
              filterValue: filterValue,
              icon: 'pi-scheduled'
            })
          }
          if (v.to) {
            let filterValue
            if (v.to.timestamp)
              filterValue = new Date(v.to.timestamp).toLocaleString()
            else if (v.to.value && v.to.unit)
              filterValue = `${v.to.value}${v.to.unit.slice(0, 1)}`

            arr.push({
              objectKey: key,
              objectLabel: `Next ${filterValue}`,
              filterKey: k,
              filterValue: filterValue,
              icon: 'pi-scheduled'
            })
          }
        } else {
          arr.push({
            objectKey: key,
            objectLabel: `${key.replace('_', ' ')}: ${v}`,
            filterKey: k,
            filterValue: v,
            icon: 'pi-search-line'
          })
        }
      }
    )
  })

  return arr
}
