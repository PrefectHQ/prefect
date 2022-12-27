import { Mapper } from '@prefecthq/orion-design'
import { maps } from '@/maps'

export const mapper = new Mapper(maps)

export type MapFunction<S, D> = (this: typeof mapper, source: S) => D