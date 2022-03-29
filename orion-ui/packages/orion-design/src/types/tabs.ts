export type Tab = {
  title: string,
  key: string,
  icon?: string,
  class?: string,
}

export type RouterTab = Tab & {
  route: {
    name: string,
    hash?: string,
  },
}

export function isRouterTab(input: Tab | RouterTab): input is RouterTab {
  return !!(input as RouterTab).route
}

type WithCount<T> = T & {
  count: number | null,
}

export type ListTab = WithCount<Tab>
export type ListRouterTab = WithCount<RouterTab>