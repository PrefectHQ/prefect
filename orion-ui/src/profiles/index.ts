import { profiles as baseProfiles } from '../../packages/orion-design/src/profiles'
import { FlowProfile } from './FlowProfile'

export const profiles = [...baseProfiles, new FlowProfile()]
