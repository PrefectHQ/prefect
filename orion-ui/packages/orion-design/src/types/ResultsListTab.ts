export type ResultsListTab = {
  label: string,
  href: string,
  count?: number,
  icon: string,
}

export type ResultsListTabWithCount = ResultsListTab & {
  count: number,
}
