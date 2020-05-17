<script>
import jsBeautify from 'js-beautify'

export default {
  props: {
    logs: {
      required: true,
      type: Array
    }
  },
  data() {
    return {
      downloadMenuOpen: false,
      downloadType: null
    }
  },
  methods: {
    // Generate a CSV string based on the currently-rendered logs
    createCsvFromLogs() {
      return this.logs
        .map(log => {
          const dateTime = `${log.date},${log.time}`
          return `${dateTime},${log.name},${log.level},"${log.message}"\n`
        })
        .join('')
    },
    // Generate a JSON string based on the currently-rendered logs
    createJsonFromLogs() {
      return jsBeautify(
        JSON.stringify(
          this.logs.map(log => ({
            date: log.date,
            time: log.time,
            level: log.level,
            name: log.name,
            message: log.message
          }))
        )
      )
    },
    // Generate a plain old string based on the currently-rendered logs
    // Used to create .txt files
    createTextFromLogs() {
      return this.logs
        .map(log => {
          const dateTime = `${log.date},${log.time}`
          return `${dateTime}\t${log.name}\t${log.level}\t${log.message}\n`
        })
        .join('')
    },
    // Create a blob and initiate a logs download for the user, based on their download menu settings
    downloadLogs() {
      let logsContent, mimeType, fileExtension

      switch (this.downloadType) {
        case 'CSV':
          logsContent = this.createCsvFromLogs()
          mimeType = 'text/csv'
          fileExtension = 'csv'
          break
        case 'JSON':
          logsContent = this.createJsonFromLogs()
          mimeType = 'application/json'
          fileExtension = 'json'
          break
        case 'Text':
          logsContent = this.createTextFromLogs()
          mimeType = 'text/plain'
          fileExtension = 'txt'
          break
        default:
          throw new Error('Unexpected file type found when downloading logs')
      }

      const blob = new Blob([logsContent], { type: mimeType })
      const link = document.createElement('a')
      link.href = window.URL.createObjectURL(blob)
      link.setAttribute('download', `logs.${fileExtension}`)
      link.click()

      this.downloadMenuOpen = false
    }
  }
}
</script>

<template>
  <v-menu
    v-model="downloadMenuOpen"
    :close-on-content-click="false"
    bottom
    left
    offset-y
    transition="slide-y-transition"
  >
    <template v-slot:activator="{ on }">
      <v-icon class="ml-4" v-on="on">
        cloud_download
      </v-icon>
    </template>
    <v-card class="download-menu-card">
      <v-card-subtitle>
        Download the logs that are currently rendered on the page.
      </v-card-subtitle>

      <div class="px-4 pt-2">
        <v-form>
          <v-select
            v-model="downloadType"
            :items="['Text', 'CSV', 'JSON']"
            :menu-props="{
              'offset-y': true,
              transition: 'slide-y-transition'
            }"
            outlined
            dense
            label="File type"
            required
          ></v-select>
        </v-form>
      </div>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn text @click="downloadMenuOpen = false">Cancel</v-btn>
        <v-btn
          text
          color="primary"
          :disabled="!downloadType"
          @click="downloadLogs"
        >
          Download
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-menu>
</template>

<style lang="scss" scoped>
.download-menu-card {
  max-width: 300px;
}
</style>
