/*
Ring 0 place nodes with alike downstream dependencies adjacent to each other
Ring 1+:
  - node initial positions are the average position of their upstream nodes
  - where possible, nodes with alike downstream dependencies are adjacent


*/

import {
  Link,
  RadarNodes,
  RadarNode,
  Rings,
  Ring,
  Links,
  Positions,
  Position,
  Items
} from '@/typings/radar'
import { max, cos, sin, sqrt, pi, floor } from './math'

function getAvailablePositions(positions: Positions): [number, Position][] {
  return Array.from(positions).filter(
    ([, position]) => position.nodes.size == 0
  )
}

function getAvailablePositionId(positions: Positions): number | undefined {
  const available = getAvailablePositions(positions)
  return available[0]?.[0]
}

export class Radar {
  private _id: string = 'id'
  private _dependencies: string = 'upstream_ids'

  nodes: RadarNodes = new Map()
  positions: Positions = new Map()
  links: Links = []
  rings: Rings = new Map()
  expandedRings: number[] = []

  baseRadius: number = 500
  channelWidth: number = 250

  // width: number = 34 // node width
  width: number = 275 // node width
  // height: number = 34 // node height
  height: number = 145 // node height

  cx: number = 0
  cy: number = 0

  /**
   *
   * @param arr [number, number]; the x and y coordinates around which to orient the graph
   * @returns instance of Radar
   */
  center([x, y]: number[]): Radar {
    this.cx = x
    this.cy = y

    return this
  }

  /**
   *
   * @param ringId string; the id of the ring to expand
   * @returns instance of Radar
   */
  expandRing(ringId: number): Radar {
    const ring = this.rings.get(ringId)
    if (!ring) {
      throw new Error('Invalid RingId when expanding ring.')
    }

    if (this.expandedRings.includes(ringId)) {
      throw new Error('Attempted to expand an already expanded ring.')
    }

    this.expandedRings.push(ringId)
    this.computeRings()
    this.computeInitialPositions()
    return this
  }

  /**
   *
   * @param key string; defines the id key accessor
   * @returns instance of Radar
   */
  id(key: string): Radar {
    this._id = key
    return this
  }

  /**
   *
   * @param key string; defines the dependencies key accessor
   * @returns instance of Radar
   */
  dependencies(key: string): Radar {
    this._dependencies = key
    return this
  }

  /**
   *
   * @param items Items; defines the items used to calculate nodes and links
   * @returns instance of Radar
   */
  items(items: Items): Radar {
    this.update(items)
    return this
  }

  /**
   *
   * @param curr RadarNode; the node from which to begin traversal
   * @param callback (optional); a callback method invoked on every node as the tree is constructed
   * @returns Map<string, RadarNode>
   */
  traverse(
    curr: RadarNode,
    callback?: (node: RadarNode) => void
  ): Map<string, RadarNode> {
    if (!curr)
      throw new Error('No starting node was provided to the traverse method.')

    const queue: [RadarNode] = [curr]
    let node: RadarNode | undefined
    const tree: Map<string, RadarNode> = new Map()

    while (queue.length > 0) {
      node = queue.shift()! // We know this will always be defined because of the while loop conditional
      callback?.(node)

      if (!node.downstreamNodes.size) {
        continue
      }

      for (const [_key, _node] of node.downstreamNodes) {
        queue.push(_node)
        tree.set(_key, node)
      }
    }

    return tree
  }

  constructor() {
    return this
  }

  private update(items: Items) {
    this.nodes = new Map()
    this.rings = new Map()
    this.links = []

    this.computeNodes(items)
    this.computeLinks()
    this.computeNodeRings()
    this.computeRings()
    this.computeInitialPositions()
  }

  private computeNodes(items: Items) {
    const len = items.length
    for (let i = 0; i < len; i++) {
      const item = items[i]
      const node = this.nodes.get(item[this._id])

      if (node) {
        this.nodes.set(item[this._id], {
          id: item[this._id],
          cx: node.cx,
          cy: node.cy,
          radian: node.radian,
          data: item,
          downstreamNodes: new Map(),
          upstreamNodes: new Map(),
          ring: node.ring
        })
      } else {
        this.nodes.set(item[this._id], {
          id: item[this._id],
          cx: 0,
          cy: 0,
          radian: 0,
          data: item,
          downstreamNodes: new Map(),
          upstreamNodes: new Map(),
          ring: 0
        })
      }
    }
  }

  private computeNodeRings() {
    const rings: [number, Ring][] = [...this.rings.entries()]

    // Populate ring nodes
    for (const [key, node] of this.nodes) {
      const ringId = this.distance(node, 'up')

      node.ring = ringId
      this.nodes.set(key, node)

      if (rings[ringId]) {
        rings[ringId][1].nodes.set(key, node)
      } else {
        rings[ringId] = [
          ringId,
          {
            radius: 0,
            nodes: new Map([[key, node]]),
            positions: new Map(),
            links: []
          }
        ]
      }
    }

    this.rings = new Map(rings)
  }

  private computeLinks() {
    for (const [key, node] of this.nodes) {
      const upstream = node.data[this._dependencies]
      const len = upstream.length

      for (let j = 0; j < len; j++) {
        const source = this.nodes.get(upstream[j][this._id])
        const link: Link = {
          target: node!,
          source: source!
        }

        node.upstreamNodes.set(upstream[j][this._id], source!)
        source!.downstreamNodes.set(key, node)

        this.nodes.set(upstream[j][this._id], source!)
        this.nodes.set(key, node)

        this.links.push(link)
      }
    }
  }

  distance(node: RadarNode, direction: 'up' | 'down'): number {
    const key: keyof RadarNode | undefined =
      direction == 'up'
        ? 'upstreamNodes'
        : direction == 'down'
        ? 'downstreamNodes'
        : undefined

    if (key == undefined)
      throw new Error(
        "Direction wasn't provided; accepted values: 'up' or 'down'."
      )

    const dfs = (node: RadarNode, depth = 0) => {
      if (node[key].size > 0) {
        const distances: number[] = []
        depth = depth + 1
        for (const [, node_] of node[key]) {
          const distance = dfs(node_, depth)
          distances.push(distance)
        }

        return Math.max(...distances)
      }

      return depth
    }

    return dfs(node)
  }

  private computeRings(start: number = 0) {
    const rings: [number, Ring][] = [...this.rings.entries()]
    // Compute ring radius and positions
    for (let i = start; i < rings.length; i++) {
      const n = rings[0][1].nodes.size
      const size = rings[i][1].nodes.size
      const prevRing = rings[i - 1]?.[1]

      let radius

      if (prevRing) {
        radius = prevRing.radius + this.baseRadius
      } else {
        radius = n === 1 ? i * this.baseRadius : (i + 1) * this.baseRadius
      }

      if (this.expandedRings.includes(i) && size > 1) {
        radius = max(
          floor((size * ((this.height + this.width) / 2)) / (pi * 2)),
          radius
        )
      }

      const positions = this.computeRingPositions(radius)
      rings[i][1].radius = radius
      rings[i][1].positions = positions

      for (let j = 0; j < positions.size; j++) {
        const position = positions.get(j)
        if (!position) continue
        this.positions.set(position.id, position)
      }
    }

    this.rings = new Map(rings)

    this.links.forEach((link: Link) => {
      const ring = this.rings.get(link.source.ring)

      if (ring) {
        ring.links.push(link)
        this.rings.set(link.source.ring, ring)
      }
    })
  }

  private computeInitialPositions() {
    if (this.rings.size === 0) return

    let _r: Ring | undefined = undefined

    for (const [key, ring] of this.rings) {
      let i = 0

      for (const [_key, node] of ring.nodes) {
        const position = this.getNodePosition(node, key, _r, i)

        node.cx = this.cx + ring.radius * Math.cos(position.radian)
        node.cy = this.cy + ring.radius * Math.sin(position.radian)

        node.radian = position.radian
        node.position = position

        position.nodes.set(node.id, node)
        ring.positions.set(position.id, position)
        this.rings.set(key, ring)
        this.nodes.set(_key, node)
        ++i
      }

      _r = ring
    }

    this.nodes = new Map(
      [...this.nodes].sort(([, aNode], [, bNode]) => {
        if (!aNode.position || !bNode.position) return 0
        return aNode.ring == bNode.ring
          ? aNode.position.id - bNode.position.id
          : aNode.ring - bNode.ring
      })
    )
  }

  private computeRingPositions(radius: number): Positions {
    const positions: Positions = new Map()

    const pow2 = (n: number) => {
      return Math.pow(n, 2)
    }

    if (radius <= 0) {
      positions.set(0, { id: 0, radian: 0, nodes: new Map(), radius: radius })
      return positions
    }

    let total = 0
    let _delta = 0

    const positionalArray = [0]
    const limit = Math.PI / 2 - (this.width * 0.8) / 2 / radius

    while (total < limit) {
      const lambda = 1.25 - 0.3 * Math.sin(total)
      const arcLength = Math.sqrt(
        pow2(this.height) * pow2(Math.cos(_delta)) +
          pow2(this.width) * pow2(Math.sin(_delta))
      )
      const delta = (lambda * arcLength) / radius

      _delta += delta
      total += delta

      // Quadrant mirroring
      if (total < limit) {
        if (total < radius / (this.channelWidth + this.width / 2)) {
          positionalArray.push(total % (2 * Math.PI)) // Lower right quad
          positionalArray.push((3 * Math.PI - total) % (2 * Math.PI)) // Lower left quad
        }
        positionalArray.push((Math.PI + total) % (2 * Math.PI)) // Upper left quad
        positionalArray.push((2 * Math.PI - total) % (2 * Math.PI)) // Upper right quad
      }
    }

    positionalArray.push(Math.PI)

    positionalArray
      .sort()
      .forEach((p: number, i: number) =>
        positions.set(i, { id: i, radian: p, nodes: new Map(), radius: radius })
      )

    return positions
  }

  private getNodePosition(
    node: RadarNode,
    rid: number,
    _r: Ring | undefined,
    node_index: number = 0
  ): Position {
    const r = this.rings.get(rid)!
    const p = r.positions
    let position

    // If the node has no upstream dependencies, we place
    // it in the first available position on the ring
    // Note: this will only happen with nodes on the innermost ring
    if (node.upstreamNodes.size === 0 || rid == 0 || rid == 1) {
      // sort first by shared downstream nodes
      // then try to place nodes with more downstream nodes as far from each other as possible
      const available = getAvailablePositions(p)

      if (node_index === 0 || node_index % 2 === 0) {
        position = p.get(available[0]?.[0])
      } else {
        position = p.get(available[Math.floor(available.length / 2)]?.[0])
      }
    } else {
      const upstream = node.upstreamNodes.entries()

      // Do this in a group?
      while (!position) {
        const [, _u] = upstream.next().value || [null, null]
        // If there are no more upstream nodes to compare against
        // we exit (and take the first available position)
        if (!_u) break

        // We get the equivalent position on the current ring
        // as this upstream node
        const equivalentPosition = Math.floor(
          (_u.position / _r!.positions.size) * p.size
        )
        const potentialPosition = p.get(equivalentPosition)

        // If this position exists and is empty, we use this position and exist early
        if (potentialPosition && potentialPosition.nodes.size === 0) {
          position = potentialPosition
          break
        }

        let i =
          equivalentPosition - 1 == 0 ? p.size - 1 : equivalentPosition - 1
        let j = equivalentPosition + 1
        while (i >= 0 || j <= p.size) {
          const downPosition = p.get(i)

          if (downPosition && downPosition.nodes.size === 0) {
            position = downPosition
            break
          }

          const upPosition = p.get(j)

          if (upPosition && upPosition.nodes.size === 0) {
            position = upPosition
            break
          }

          i--
          j++
        }
      }
    }

    if (!position) {
      const positionId = getAvailablePositionId(p)
      position =
        typeof positionId !== 'undefined'
          ? p.get(positionId)!
          : p.get(p.size - 1)!
    }

    return position
  }
}
