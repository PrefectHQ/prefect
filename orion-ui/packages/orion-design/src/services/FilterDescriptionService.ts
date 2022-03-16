import { Filter, FilterObject, FilterProperty } from '@/types/filters'

export class FilterDescriptionService {
  public static describe(filter: Filter): string {
    const description: string[] = [
      'Show',
      this.object(filter.object),
      'by',
      this.property(filter.property),
    ]


    return description.join(' ').trim()
  }

  public static object(object: FilterObject): string {
    switch (object) {
      case 'flow':
        return 'flows'
      case 'deployment':
        return 'deployments'
      case 'flow_run':
        return 'flow runs'
      case 'task_run':
        return 'task runs'
      case 'tag':
        return 'tags'
    }
  }

  private static property(property: FilterProperty | undefined): string {
    switch (property) {
      case 'tag':
        return 'tag'
      case 'name':
        return 'name'
      case 'start_date':
        return 'start date'
      case 'state':
        return 'state'
      case undefined:
        return '...'
    }
  }
}