/*
Why? momentDurationFormat is a plugin for moment.js
Because plugins for moment look for the defined moment instance by default, I'd like to use this file to install plugins for moment and then export particular functions from moment so that I can use plugins from those functions.

For example, with the code below Vue components can now:
import { duration } from '@/utils/moment'
and use duration({{ input }}).format() without having to import moment and moment-duration-format.
*/
import moment from 'moment'
// eslint-disable-next-line no-unused-vars
import momentDurationFormat from 'moment-duration-format'

export const duration = moment.duration

export default moment
