import { GlobalFilter } from '@/typings/global'

export type FilterObject = {
  objectKey: string
  objectLabel: string
  filterKey: string
  filterValue: any
  icon: string
  clearable?: boolean
}

// TODO: This is really messy, need to clean this up a lot.

export const parseFilters = (gf: GlobalFilter) => {
  const arr: FilterObject[] = []
  const keys = Object.keys(gf)
  keys.forEach((key) => {
    Object.entries(gf[key as keyof GlobalFilter]).forEach(
      ([k, v]: [string, any]) => {
        if (k == 'states' && Array.isArray(v)) {
          if (v.length == 6 || v.length == 0) {
            let objectLabel
            if (v.length == 6) objectLabel = 'All States'
            else objectLabel = 'No states'

            arr.push({
              objectKey: key,
              objectLabel: objectLabel,
              filterKey: k,
              filterValue: v,
              icon: 'pi-focus-3-line',
              clearable: v.length === 0
            })
          } else {
            v.forEach((state) => {
              arr.push({
                objectKey: key,
                objectLabel: state.name.toLowerCase(),
                filterKey: k,
                filterValue: v,
                icon: 'pi-focus-3-line',
                clearable: true
              })
            })
          }
        } else if (k == 'timeframe') {
          if (v.from) {
            let filterValue
            if (v.from.timestamp)
              filterValue = new Date(v.from.timestamp).toLocaleString()
            else if (v.from.value && v.from.unit)
              filterValue = `${v.from.value}${v.from.unit.slice(0, 1)}`

            // TODO: We should use a different icon or indicator for flow run and task run timeframes
            arr.push({
              objectKey: key,
              objectLabel: `Past ${filterValue}`,
              filterKey: k,
              filterValue: filterValue,
              icon: 'pi-scheduled',
              clearable: true
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
              icon: 'pi-scheduled',
              clearable: true
            })
          }
        } else {
          arr.push({
            objectKey: key,
            objectLabel: `${key.replace('_', ' ')}: ${v}`,
            filterKey: k,
            filterValue: v,
            icon: 'pi-search-line',
            clearable: true
          })
        }
      }
    )
  })

  return arr
}
