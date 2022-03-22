export type Tab = {
  title: string,
  key: string,
  icon?: string,
  class?: string,
}

type Route = {
  name: string,
  hash?: string,
}

export type RouterTab = {
  title: string,
  key: string,
  route: Route,
  icon?: string,
  class?: string,
}

export function isRouterTab(input: Tab | RouterTab): input is RouterTab {
  return !!(input as RouterTab).route
}

type WithCount<T> = T & {
  count: number,
}

export type ListTab = WithCount<Tab>
export type ListRouterTab = WithCount<RouterTab>