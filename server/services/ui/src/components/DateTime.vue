<script>
import moment from 'moment-timezone'
import range from 'lodash.range'

export default {
  props: {
    warning: {
      type: String,
      required: true
    },
    label: {
      type: String,
      required: true
    },
    hint: {
      type: String,
      required: true
    }
  },
  data() {
    return {
      // Track current date & time for run scheduling purposes
      currentDateTimeMoment: null,

      // date/time input
      date: null,
      showTimeMenu: false,
      startTimeTab: 'date',
      timeHr: '12',
      timeMin: '00',
      timeAmPm: 'AM',
      // This is a placeholder for now, since we don't yet have a way to set timezone
      // across the system
      timezone: null
    }
  },
  computed: {
    currentDate() {
      if (!this.currentDateTimeMoment) return null

      return this.currentDateTimeMoment.format('YYYY-MM-DD')
    },
    // Scheduled start date/time that will be sent as part of mutation
    dateTime() {
      if (!this.dateTimeMoment) return null

      // If user's timezone is not set, format to ISO 8601 and return
      if (!this.timezone) return this.dateTimeMoment.format()

      // If user's timezone is set...
      return (
        this.dateTimeMoment
          // format to ISO 8601
          .format()
          // Remove timezone identifier (-05:00, Z, etc)
          .replace(/([+|-]\d{2}:\d{2})|Z$/g, '')
          // Append new timezone identifier based on user's timezone
          .concat(
            moment()
              .tz(this.timezone)
              .format('Z')
          )
      )
    },
    dateTimeMoment() {
      if (!this.date) return null

      const dateTime = `${this.date} ${this.timeHr}:${this.timeMin} ${this.timeAmPm}`

      return moment(dateTime)
    },
    // Scheduled start date/time formatted for display on date/time input
    formatted() {
      if (!this.dateTimeMoment) return null

      return `${this.dateTimeMoment.format('MMMM D YYYY [at] h:mm A')} ${
        this.timezone
          ? moment()
              .tz(
                this.timezone ||
                  Intl.DateTimeFormat().resolvedOptions().timeZone
              )
              .zoneAbbr()
          : ''
      }`
    },
    timeInPast() {
      if (!this.dateTimeMoment) return false

      return this.dateTimeMoment < this.currentDateTimeMoment
    }
  },
  created() {
    this.currentDateTimeMoment = this.timezone
      ? moment().tz(this.timezone)
      : moment()

    setInterval(() => {
      this.currentDateTimeMoment = this.timezone
        ? moment().tz(this.timezone)
        : moment()
    }, 5000)
  },
  methods: {
    timeRange(min, max) {
      return range(min, max).map(val => {
        if (val < 10) return `0${val}`
        return val.toString()
      })
    },
    handleDateChange(input) {
      this.date = input
      this.startTimeTab = 'time'

      let currentDateTime = this.timezone
        ? moment().tz(this.timezone)
        : moment()

      currentDateTime.add(1, 'minute')

      if (this.date === currentDateTime.format('YYYY-MM-DD')) {
        // If selected date is current day,
        // set time input values as the current time + 1 minute.
        this.timeHr = currentDateTime.format('hh')
        this.timeMin = currentDateTime.format('mm')
        this.timeAmPm = currentDateTime.format('A')
      } else {
        // If selected day is in the future,
        // initialize start time as midnight.
        this.timeHr = '12'
        this.timeMin = '00'
        this.timeAmPm = 'AM'
      }
    },
    handleDateTimeClear() {
      this.date = null
      this.startTimeTab = 'date'
    },
    submitDateTime() {
      this.showTimeMenu = false
      this.$emit('selectDateTime', this.dateTime)
    }
  }
}
</script>

<template>
  <div class="mb-8">
    <v-menu
      v-model="showTimeMenu"
      max-width="290"
      offset-y
      :close-on-click="false"
      :close-on-content-click="false"
    >
      <template v-slot:activator="{ on }">
        <v-text-field
          :value="formatted"
          clearable
          readonly
          :label="label"
          :hint="hint"
          persistent-hint
          v-on="on"
          @click:clear="handleDateTimeClear"
        ></v-text-field>
      </template>
      <v-tabs v-model="startTimeTab" grow class="tab-height-custom">
        <v-tab key="date" href="#date">Date</v-tab>
        <v-tab key="time" href="#time" :disabled="!date">
          Time
        </v-tab>

        <!-- <v-tabs-slider color="blue"></v-tabs-slider> -->

        <v-tab-item value="date">
          <v-date-picker
            v-model="date"
            no-title
            :min="currentDate"
            label="Hour"
            @change="handleDateChange"
          ></v-date-picker>
        </v-tab-item>

        <v-tab-item value="time">
          <v-card tile>
            <v-card-text>
              <v-row>
                <v-col cols="4">
                  <v-autocomplete
                    v-model="timeHr"
                    hide-details
                    label="Hour"
                    :items="timeRange(1, 13)"
                    :append-icon="null"
                    hide-no-data
                  ></v-autocomplete>
                </v-col>
                <v-col cols="4">
                  <v-autocomplete
                    v-model="timeMin"
                    hide-details
                    label="Minute"
                    :items="timeRange(0, 60)"
                    :append-icon="null"
                    hide-no-data
                  ></v-autocomplete>
                </v-col>
                <v-col cols="4">
                  <v-autocomplete
                    v-model="timeAmPm"
                    hide-details
                    label="AM/PM"
                    :items="['AM', 'PM']"
                    :append-icon="null"
                    hide-no-data
                  ></v-autocomplete>
                </v-col>
              </v-row>
              <v-row>
                <v-col cols="12">
                  <p>Timezone: {{ timezone || 'Local' }}</p>
                </v-col>
              </v-row>
              <v-row>
                <v-col cols="12" class="py-0">
                  <v-scroll-x-transition>
                    <v-alert
                      v-if="timeInPast"
                      border="left"
                      colored-border
                      elevation="2"
                      type="warning"
                      dense
                      class="mt-4 mb-0"
                    >
                      <span class="body-2 ma-0">
                        {{ warning }}
                      </span>
                    </v-alert>
                  </v-scroll-x-transition>
                </v-col>
              </v-row>
            </v-card-text>
            <v-card-actions>
              <v-spacer></v-spacer>
              <v-btn text color="primary" @click="submitDateTime">
                Confirm
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-tab-item>
      </v-tabs>
    </v-menu>
  </div>
</template>
