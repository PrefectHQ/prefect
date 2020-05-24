// Base imports
import Vue from 'vue'
import vuetify from '@/plugins/vuetify'
import '@/plugins/apex-charts'
import Router from 'vue-router'
import App from '@/App.vue'
import router from '@/router'
import store from '@/store'
// Plugins
import { createApolloProvider } from './vue-apollo'
import Toasted from 'vue-toasted'
// Filters
import displayTime from '@/filters/displayTime'
import displayDate from '@/filters/displayDate'
import displayLocalDate from '@/filters/displayLocalDate'
import displayDateTime from '@/filters/displayDateTime'
import displayHowLongAgo from '@/filters/displayHowLongAgo'
import displayTimeDayMonthYear from '@/filters/displayTimeDayMonthYear'
import duration from '@/filters/duration'
import number from '@/filters/number'
import {
  roundWhole,
  roundTenths,
  roundHundredths,
  roundThousandths,
  roundTens,
  roundHundreds,
  roundThousands
} from '@/filters/round'
import shorten from '@/filters/shorten'
import filterOnePercent from '@/filters/filterOnePercent'

Vue.config.productionTip = false

// moved here to facilitate testing
Vue.use(Router)

Vue.use(Toasted, {
  router
})

// Add Filters
Vue.filter('displayTime', displayTime)
Vue.filter('displayLocalDate', displayLocalDate)
Vue.filter('displayDate', displayDate)
Vue.filter('displayDateTime', displayDateTime)
Vue.filter('displayHowLongAgo', displayHowLongAgo)
Vue.filter('displayTimeDayMonthYear', displayTimeDayMonthYear)
Vue.filter('duration', duration)
Vue.filter('shorten', shorten)
Vue.filter('number', number)
Vue.filter('filterOnePercent', filterOnePercent)

Vue.filter('roundWhole', roundWhole)
Vue.filter('roundTenths', roundTenths)
Vue.filter('roundHundredths', roundHundredths)
Vue.filter('roundThousandths', roundThousandths)
Vue.filter('roundTens', roundTens)
Vue.filter('roundHundreds', roundHundreds)
Vue.filter('roundThousands', roundThousands)

// Create application
new Vue({
  vuetify,
  router,
  store,
  apolloProvider: createApolloProvider(),
  render: h => h(App)
}).$mount('#app')
