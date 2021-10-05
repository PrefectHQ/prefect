/*
Ring 0 place nodes with alike downstream dependencies adjacent to each other
Ring 1+:
  - node initial positions are the average position of their upstream nodes
  - where possible, nodes with alike downstream dependencies are adjacent


*/

import {
  Link,
  SchematicNodes,
  SchematicNode,
  Rings,
  Ring,
  Links,
  Positions,
  Position,
  Items
} from '@/typings/schematic'

function defaultId(d: any) {
  // We could use d.index for this since this is a map
  // but we'll assume UUIDs for now
  return d.id
}

function getAvailablePositions(positions: Positions): [number, Position][] {
  return Array.from(positions).filter(
    ([key, position]) => position.nodes.size == 0
  )
}

function getAvailablePositionId(positions: Positions): number | undefined {
  const available = getAvailablePositions(positions)
  return available[0]?.[0]
}

export class RadialSchematic {
  id = defaultId

  nodes: SchematicNodes = new Map()
  links: Links = []

  baseRadius: number = 300
  maxRecomputations: number = 6

  /* Extent */
  x0: number = 0
  y0: number = 0
  x1: number = 1
  y1: number = 1

  width: number = 188 // node width
  height: number = 53 // node height

  /* Padding */
  py: number = 0
  px: number = 0

  cx: number = 0
  cy: number = 0

  rings: Rings = new Map()

  center([x, y]: number[]): RadialSchematic {
    this.cx = x
    this.cy = y

    return this
  }

  computations(c: number): RadialSchematic {
    this.maxRecomputations = c

    return this
  }

  items(items: Items): RadialSchematic {
    this.update(items)
    return this
  }

  traverse(
    curr: SchematicNode,
    callback?: (node: SchematicNode) => void
  ): Map<string, SchematicNode> {
    if (!curr)
      throw new Error('No starting node was provided to the traverse method.')

    const queue: [SchematicNode] = [curr]
    let node: SchematicNode | undefined
    const tree: Map<string, SchematicNode> = new Map()

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
    this.links = []
    this.rings = new Map()

    this.computeNodes(items)
    this.computeLinks()
    this.computeRings()
    this.computeInitialPositions()
    // this.computeIdealPositions()
  }

  private computeNodes(items: Items) {
    const len = items.length
    for (let i = 0; i < len; i++) {
      const item = items[i]
      this.nodes.set(item.id, {
        id: item.id,
        cx: 0,
        cy: 0,
        radian: 0,
        data: item,
        downstreamNodes: new Map(),
        upstreamNodes: new Map(),
        ring: 0,
        position: 0
      })
    }
  }

  private computeLinks() {
    for (const [key, node] of this.nodes) {
      const upstream = node.data.upstream_ids
      const len = upstream.length

      for (let j = 0; j < len; j++) {
        const source = this.nodes.get(upstream[j])
        const link: Link = {
          target: node!,
          source: source!
        }

        node.upstreamNodes.set(upstream[j], source!)
        source!.downstreamNodes.set(key, node)

        this.nodes.set(upstream[j], source!)
        this.nodes.set(key, node)

        this.links.push(link)
      }
    }
  }

  private computeRings() {
    const rings: [number, Ring][] = []

    // Populate ring nodes
    for (const [key, node] of this.nodes) {
      const ringId: number =
        node.upstreamNodes.size > 0
          ? Array.from(node.upstreamNodes).reduce<number>(
              (acc: number, [key, _node]: [string, SchematicNode]) =>
                _node.ring >= acc && _node.ring > 0 ? _node.ring + 1 : acc,
              1
            )
          : 0

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
            positions: new Map()
          }
        ]
      }
    }

    // Compute ring radius and positions
    for (let i = 0; i < rings.length; i++) {
      const n = rings[0][1].nodes.size
      const radius = n === 1 ? i * this.baseRadius : (i + 1) * this.baseRadius

      rings[i][1].radius = radius
      rings[i][1].positions = this.computeRingPositions(radius)
      // rings[i][1].nodes = new Map(
      //   [...rings[i][1].nodes].sort(
      //     ([aKey, aNode], [bKey, bNode]) => aNode.position - bNode.position
      //   )
      // )
    }

    this.rings = new Map(rings)
  }

  private computeInitialPositions() {
    if (this.rings.size === 0) return

    let _r: Ring | undefined = undefined

    for (const [key, ring] of this.rings) {
      for (const [_key, node] of ring.nodes) {
        const position = this.getNodePosition(node, key, _r)

        node.cx = this.cx + ring.radius * Math.cos(position.radian)
        node.cy = this.cy + ring.radius * Math.sin(position.radian)

        node.radian = position.radian
        node.position = position.id

        position.nodes.set(node.id, node)
        ring.positions.set(position.id, position)
        this.rings.set(key, ring)
        this.nodes.set(_key, node)
      }

      _r = ring
    }

    this.nodes = new Map(
      [...this.nodes].sort(([aKey, aNode], [bKey, bNode]) =>
        aNode.ring == bNode.ring
          ? aNode.position - bNode.position
          : aNode.ring - bNode.ring
      )
    )
  }

  private computeRingPositions(radius: number): Positions {
    const nPositions =
      Math.floor((2 * Math.PI * radius) / (this.width * 1.5)) + 1
    const increment = 360 / nPositions
    const positions: Positions = new Map()

    for (let i = 0; i < nPositions; i++) {
      const radian = (increment * i * Math.PI) / 180
      positions.set(i, { id: i, radian: radian, nodes: new Map() })
    }

    return positions
  }

  private getNodePosition(
    node: SchematicNode,
    rid: number,
    _r: Ring | undefined
  ): Position {
    const r = this.rings.get(rid)!
    const p = r.positions
    let position

    // If the node has no upstream dependencies, we place
    // it in the first available position on the ring
    // Note: this will only happen with nodes on the innermost ring
    if (node.upstreamNodes.size === 0) {
      // sort first by shared downstream nodes
      // then try to place nodes with more downstream nodes as far from each other as possible
      const available = getAvailablePositions(p)
      position = p.get(available[Math.floor(available.length / 2)]?.[0])
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
