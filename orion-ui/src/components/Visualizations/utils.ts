export const createCappedBar = (
  options: {
    capTop: Boolean
    capBottom: Boolean
    x: number
    y: number
    height: number
    width: number
    radius: number
  } = {
    capTop: true,
    capBottom: true,
    x: 0,
    y: 0,
    height: 0,
    width: 0,
    radius: 1
  }
): string => {
  const { capTop, capBottom, height, width, x, y, radius } = options

  const cT = capTop
    ? `a ${radius} ${radius} 0 1 0 -${width} 0`
    : `a 0 0 0 1 0 -${width} 0`
  const cB = capBottom
    ? `a ${radius} ${radius} 0 1 0 ${width} 0`
    : `a 0 0 0 1 0 ${width} 0`

  return `M${x},${y} v${height} ${cB} ${
    capBottom ? '' : `h${width}`
  } v-${height} ${cT}`
}
