export declare interface Link {
  source: SchematicNode
  target: SchematicNode
}

export declare interface SchematicNode {
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

export declare interface Item {
  id: string
  name: string
  upstream_ids: string[]
  state: string
  tags: string[]
  start_time: string
  end_time: string
}

export declare interface Position {
  id: number
  radian: number
  nodes: SchematicNodes
}

export declare interface Ring {
  nodes: SchematicNodes
  radius: number
  positions: Positions
}

export declare type Positions = Map<number, Position>
export declare type Rings = Map<number, Ring>
export declare type Items = Item[]
export declare type SchematicNodes = Map<string, SchematicNode>
export declare type Links = Link[]
