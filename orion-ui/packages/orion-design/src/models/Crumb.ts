import { RouteLocationRaw } from 'vue-router'

export type Crumb = {
  text: string,
  loading?: boolean,
  clickable?: boolean,
  to?: RouteLocationRaw,
}
