import * as d3 from 'd3'
import { pi } from './math'

import { Ring } from '@/typings/radar'

export type Arc = {
  start: number
  end: number
  radius: number
  state: string | null
}

export const calculateArcSegment = (arc: Arc): string => {
  const r = arc.radius
  const cx = 100
  const cy = 100

  const path = d3.path()

  path.arc(cx, cy, r, arc.start, arc.end, false)
  return path.toString()
}

export const generateArcs = (
  [, d]: [number, Ring],
  baseRadius: number
): Arc[] => {
  const arcs: Arc[] = []

  const r = d.radius
  const channel = 125

  const channelAngle = (channel * 360) / (2 * pi * r || 10)

  // Convert start/end angles to radians
  const startTheta = ((90 - channelAngle) * pi) / 180
  const endTheta = ((90 + channelAngle) * pi) / 180

  let theta = d.positions.get(d.positions.size - 1)?.radian || 0

  for (const [, position] of d.positions) {
    const positionalArr = [...position.nodes.values()]
    const state = positionalArr?.[0]?.data?.state?.type?.toLowerCase()

    if (r == 0) {
      // This is only for the innermost ring for radars with a single root node
      arcs.push({
        start: (115 * pi) / 180,
        end: (65 * pi) / 180,
        radius: baseRadius / 4,
        state: state || null
      })
    } else if (position.radian > startTheta && theta < endTheta) {
      arcs.push({
        start: theta,
        end: startTheta,
        radius: r,
        state: null
      })
      arcs.push({
        start: endTheta,
        end: position.radian,
        radius: r,
        state: state || null
      })
    } else {
      arcs.push({
        start: theta,
        end: position.radian,
        radius: r,
        state: state || null
      })
    }
    theta = position.radian
  }
  return arcs
}
