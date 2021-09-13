declare interface Link {
  source: SchematicNode
  target: SchematicNode
}

declare interface SchematicNode {
  id: string
  cx: number
  cy: number
  radian: number
  data: any
  downstreamNodes: Map<string, SchematicNode>
  upstreamNodes: Map<string, SchematicNode>
  ring: number
  position: number
}

declare interface Item {
  id: string
  name: string
  upstream_ids: string[]
  state: string
  tags: string[]
  start_time: string
  end_time: string
}

declare interface Position {
  id: number
  radian: number
  nodes: SchematicNodes
}

declare interface Ring {
  nodes: SchematicNodes
  radius: number
  positions: Positions
}

declare type Positions = Map<number, Position>
declare type Rings = Map<number, Ring>
declare type Items = Item[]
declare type SchematicNodes = Map<string, SchematicNode>
declare type Links = Link[]
