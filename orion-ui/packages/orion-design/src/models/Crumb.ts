export type Crumb = {
  text: string,
  // to?: used to expect string | undefined, but nebula routes return AppRouteLocation
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  to?: any,
}
