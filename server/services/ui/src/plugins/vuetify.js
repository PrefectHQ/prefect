import { STATE_COLORS } from '@/utils/states'
import Vue from 'vue'
import Vuetify from 'vuetify/lib'

export const THEME_COLORS = {
  prefect: '#27b1ff', // prefect blue
  primary: '#3b8dff', // primary blue
  primaryDark: '#0075b8',
  primaryLight: '#e0f4ff',
  secondaryGray: '#465968',
  secondaryGrayDark: '#1d252b',
  secondaryGrayLight: '#edf0f3',
  accentPink: '#fe5196',
  accentCyan: '#2edaff',
  accentGreen: '#07e798',
  accentOrange: '#f77062',
  codePink: '#da2072',
  codeBlue: '#0073df',
  codeBlueBright: '#004bff',
  UIPrimaryBlue: '#007acc',
  UIPrimaryDark: '#003d66',
  UIPrimaryLight: '#e0f3ff',
  secondaryBlue: '#3b8dff',
  plan: '#2edaff',
  tertiaryBlue: '#0076ff',
  secondary: '#2F383F', // primary grey-light
  accent: '#1b5da4', // accent blue
  'accent-pink': '#fe5196',
  error: '#FF5252', // alerts error
  info: '#2196F3', // vuetify default
  success: '#4CAF50', // alerts success
  warning: '#FFC107', // alerts warning
  deepRed: '#B00000',
  failRed: '#D50000',
  appBackground: '#f9f9f9'
}

export const THEME_COLORS_ALT = {
  appBackground: '#f9f9f9',
  prefect: '#003d66',
  primary: '#007acc'
}

Vue.use(Vuetify)

export default new Vuetify({
  icons: {
    iconfont: 'md'
  },
  theme: {
    options: {
      customProperties: true
    },
    themes: {
      light: Object.assign({}, THEME_COLORS, STATE_COLORS),
      dark: Object.assign({}, THEME_COLORS, THEME_COLORS_ALT, STATE_COLORS)
    }
  }
})
