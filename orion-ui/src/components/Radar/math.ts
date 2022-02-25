export const { abs } = Math
export const { atan2 } = Math
export const { cos } = Math
export const { max } = Math
export const { min } = Math
export const { sin } = Math
export const { tan } = Math
export const { sqrt } = Math
export const { pow } = Math
export const { floor } = Math
export const { ceil } = Math

export const epsilon = 1e-12
export const pi = Math.PI
export const halfPi = pi / 2
export const tau = 2 * pi

export const acos = (x: number): number => {
  return x > 1 ? 0 : x < -1 ? pi : Math.acos(x)
}

export const asin = (x: number): number => {
  return x >= 1 ? halfPi : x <= -1 ? -halfPi : Math.asin(x)
}

export const pow2 = (n: number): number => {
  return n**2
}
