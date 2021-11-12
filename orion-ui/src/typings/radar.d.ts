export declare interface Link {
  source: RadarNode
  target: RadarNode
}

export declare interface RadarNode {
  id: string
  cx: number
  cy: number
  radian: number
  data: any
  downstreamNodes: Map<string, RadarNode>
  upstreamNodes: Map<string, RadarNode>
  siblingNodes: Map<string, RadarNode>
  ring: number
  position?: Position
}

export declare interface Item {
  task_run_id: string
  upstream_dependencies: Item[]
  [key: string]: any
}

export declare interface Position {
  id: number
  radian: number
  nodes: RadarNodes
  radius: number
}

export declare interface Ring {
  nodes: RadarNodes
  radius: number
  expanded?: boolean
  positions: Positions
  links: Link[]
}

export declare type Positions = Map<number, Position>
export declare type Rings = Map<number, Ring>
export declare type Items = Item[]
export declare type RadarNodes = Map<string, RadarNode>
export declare type Links = Link[]
