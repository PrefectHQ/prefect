<script>
import moment from 'moment-timezone'
import range from 'lodash.range'

// A RegEx for checking 12-hour time formats
// e.g. 1:14:18am, 11:23:34 PM
const TIME_FORMAT = /^((?:0?[1-9]|1[0-2]):[0-5]\d:[0-5]\d\s*(a|A|p|P)(m|M)\s*$)$/

export default {
  props: {
    menuOpen: {
      required: true,
      type: Boolean
    },
    logLevels: {
      required: true,
      type: Array
    }
  },
  data() {
    return {
      open: this.menuOpen,
      filterFormDatetimeError: null,
      searchInput: '',
      logLevelFilterInput: this.logLevels,

      dateFromInput: null,
      dateFromMenu: false,
      timeFromInputAmPm: 'AM',
      timeFromInputHr: '12',
      timeFromInputMin: '00',
      timeFromInputSec: '00',
      timeFromMenu: false,
      timeFromValid: true,

      dateToInput: null,
      dateToMenu: false,
      timeToInputAmPm: moment().format('A'),
      timeToInputHr: moment().format('hh'),
      timeToInputMin: moment().format('mm'),
      timeToInputSec: moment().format('ss'),
      timeToMenu: false,
      timeToValid: true
    }
  },
  computed: {
    timeFromInput() {
      return (
        `${this.timeFromInputHr}:` +
        `${this.timeFromInputMin}:` +
        `${this.timeFromInputSec} ${this.timeFromInputAmPm}`
      )
    },
    timeToInput() {
      return (
        `${this.timeToInputHr}:` +
        `${this.timeToInputMin}:` +
        `${this.timeToInputSec} ${this.timeToInputAmPm}`
      )
    }
  },
  watch: {
    menuOpen() {
      this.open = this.menuOpen
    },
    open() {
      if (this.open) {
        this.$emit('open')
      } else {
        this.$emit('close')
      }
    }
  },
  methods: {
    endDatePlaceholder() {
      return moment().format('YYYY-MM-DD')
    },
    handleDateChange(fromOrTo) {
      this.filterFormDatetimeError = null

      if (fromOrTo === 'from') {
        this.dateFromMenu = false
      }

      if (fromOrTo === 'to') {
        this.dateToMenu = false
      }
    },
    handleDateClear(fromOrTo) {
      this.filterFormDatetimeError = null

      if (fromOrTo === 'from') {
        this.dateFromInput = null
        this.timeFromInputHr = '12'
        this.timeFromInputMin = '00'
        this.timeFromInputSec = '00'
        this.timeFromInputAmPm = 'AM'
      }

      if (fromOrTo === 'to') {
        this.dateToInput = null
        this.timeToInputHr = moment().format('hh')
        this.timeToInputMin = moment().format('mm')
        this.timeToInputSec = moment().format('ss')
        this.timeToInputAmPm = moment().format('A')
      }
    },
    handleFilter() {
      this.filterFormDatetimeError = null

      let startDateTime
      let endDateTime

      if (this.dateFromInput) {
        let newTimeFrom = this.dateFromInput
        if (this.timeFromInput && this.timeInputValid(this.timeFromInput)) {
          newTimeFrom = `${newTimeFrom} ${this.timeFromInput}`
        }
        startDateTime = moment(newTimeFrom)
      }

      if (this.dateToInput) {
        let newTimeTo = this.dateToInput
        if (this.timeToInput && this.timeInputValid(this.timeToInput)) {
          newTimeTo = `${newTimeTo} ${this.timeToInput}`
        }
        endDateTime = moment(newTimeTo)
      }

      if (startDateTime && endDateTime && startDateTime > endDateTime) {
        this.filterFormDatetimeError = [
          'Invalid date and time range. Please try again.'
        ]
        return
      }

      this.$emit('filter', {
        searchInput: this.searchInput,
        logLevelFilterInput: this.logLevelFilterInput,
        startDateTime,
        endDateTime
      })

      this.open = false
    },
    resetFilter() {
      this.searchInput = ''
      this.logLevelFilterInput = this.logLevels
      this.handleDateClear('from')
      this.handleDateClear('to')
      this.handleFilter()
    },
    timeInputValid(time) {
      return TIME_FORMAT.test(time)
    },
    // Create a array of consecutive numbers
    // Add paddings to any single-digit numbers, so 1 becomes "01"
    // Keep double-digit numbers as-is
    timeRange(min, max) {
      return range(min, max).map(val => {
        if (val < 10) return `0${val}`
        return val.toString()
      })
    }
  }
}
</script>

<template>
  <v-menu
    v-model="open"
    :close-on-content-click="false"
    bottom
    left
    offset-y
    transition="slide-y-transition"
  >
    <template v-slot:activator="{ on }">
      <v-icon class="ml-4" v-on="on">
        filter_list
      </v-icon>
    </template>
    <v-card class="px-5 pt-3 filter-menu-card">
      <v-form>
        <v-row dense>
          <v-col cols="12">
            <v-text-field
              v-model="searchInput"
              dense
              outlined
              label="Search logs by text"
              clearable
            ></v-text-field>
          </v-col>
          <v-col cols="12">
            <v-select
              v-model="logLevelFilterInput"
              :items="logLevels"
              :menu-props="{
                'min-width': 200,
                'offset-y': true,
                transition: 'slide-y-transition'
              }"
              multiple
              chips
              deletable-chips
              small-chips
              dense
              outlined
              label="Log level"
            ></v-select>
          </v-col>
          <v-col cols="12" md="6">
            <v-menu
              v-model="dateFromMenu"
              :close-on-content-click="false"
              max-width="290"
              offset-y
            >
              <template v-slot:activator="{ on }">
                <v-text-field
                  :value="dateFromInput"
                  :error-messages="filterFormDatetimeError"
                  clearable
                  label="Starting date"
                  readonly
                  dense
                  outlined
                  placeholder="2017-03-23"
                  v-on="on"
                  @click:clear="handleDateClear('from')"
                ></v-text-field>
              </template>
              <v-date-picker
                v-model="dateFromInput"
                no-title
                @change="handleDateChange('from')"
              ></v-date-picker>
            </v-menu>
          </v-col>
          <v-col cols="12" md="6" class="pt-0">
            <v-row v-if="dateFromInput" dense>
              <v-col cols="3">
                <v-autocomplete
                  v-model="timeFromInputHr"
                  class="ma-0"
                  dense
                  outlined
                  :append-icon="null"
                  hide-no-data
                  hide-details
                  label="Hour"
                  :items="timeRange(1, 13)"
                  :error="!!filterFormDatetimeError"
                ></v-autocomplete>
              </v-col>
              <v-col cols="3">
                <v-autocomplete
                  v-model="timeFromInputMin"
                  class="ma-0"
                  dense
                  outlined
                  :append-icon="null"
                  hide-no-data
                  hide-details
                  label="Minutes"
                  :items="timeRange(0, 60)"
                  :error="!!filterFormDatetimeError"
                ></v-autocomplete>
              </v-col>
              <v-col cols="3">
                <v-autocomplete
                  v-model="timeFromInputSec"
                  class="ma-0"
                  dense
                  outlined
                  :append-icon="null"
                  hide-no-data
                  hide-details
                  label="Seconds"
                  :items="timeRange(0, 60)"
                  :error="!!filterFormDatetimeError"
                ></v-autocomplete>
              </v-col>
              <v-col cols="3">
                <v-autocomplete
                  v-model="timeFromInputAmPm"
                  class="ma-0"
                  dense
                  outlined
                  :append-icon="null"
                  hide-no-data
                  hide-details
                  label="AM/PM"
                  :items="['AM', 'PM']"
                  :error="!!filterFormDatetimeError"
                ></v-autocomplete>
              </v-col>
            </v-row>
          </v-col>
          <v-col cols="12" md="6">
            <v-menu
              v-model="dateToMenu"
              :close-on-content-click="false"
              max-width="290"
              offset-y
            >
              <template v-slot:activator="{ on }">
                <v-text-field
                  :error-messages="filterFormDatetimeError"
                  :placeholder="endDatePlaceholder()"
                  :value="dateToInput"
                  clearable
                  label="Ending date"
                  readonly
                  dense
                  outlined
                  v-on="on"
                  @click:clear="handleDateClear('to')"
                ></v-text-field>
              </template>
              <v-date-picker
                v-model="dateToInput"
                no-title
                @change="handleDateChange('to')"
              ></v-date-picker>
            </v-menu>
          </v-col>
          <v-col cols="12" md="6" class="pt-0">
            <v-row v-if="dateToInput" dense>
              <v-col cols="3">
                <v-autocomplete
                  v-model="timeToInputHr"
                  class="ma-0"
                  dense
                  outlined
                  :append-icon="null"
                  hide-no-data
                  hide-details
                  label="Hour"
                  :items="timeRange(1, 13)"
                  :error="!!filterFormDatetimeError"
                ></v-autocomplete>
              </v-col>
              <v-col cols="3">
                <v-autocomplete
                  v-model="timeToInputMin"
                  class="ma-0"
                  dense
                  outlined
                  :append-icon="null"
                  hide-no-data
                  hide-details
                  label="Minutes"
                  :items="timeRange(0, 60)"
                  :error="!!filterFormDatetimeError"
                ></v-autocomplete>
              </v-col>
              <v-col cols="3">
                <v-autocomplete
                  v-model="timeToInputSec"
                  class="ma-0"
                  dense
                  outlined
                  :append-icon="null"
                  hide-no-data
                  hide-details
                  label="Seconds"
                  :items="timeRange(0, 60)"
                  :error="!!filterFormDatetimeError"
                ></v-autocomplete>
              </v-col>
              <v-col cols="3">
                <v-autocomplete
                  v-model="timeToInputAmPm"
                  class="ma-0"
                  dense
                  outlined
                  :append-icon="null"
                  hide-no-data
                  hide-details
                  label="AM/PM"
                  :items="['AM', 'PM']"
                  :error="!!filterFormDatetimeError"
                ></v-autocomplete>
              </v-col>
            </v-row>
          </v-col>
        </v-row>
      </v-form>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn text @click="open = false">Close</v-btn>
        <v-btn text @click="resetFilter">
          Reset
        </v-btn>
        <v-btn text color="primary" @click="handleFilter">
          Apply
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-menu>
</template>

<style scoped lang="scss">
.filter-menu-card {
  max-width: 768px;
  min-width: 300px;
}
</style>

<style lang="scss">
.filter-menu-card {
  .v-label.v-label--active {
    background-color: #fff;
  }
}
</style>
