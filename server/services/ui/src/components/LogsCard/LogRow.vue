<script>
export default {
  props: {
    index: {
      type: Number,
      required: true
    },
    log: {
      type: Object,
      required: true
    }
  },
  data() {
    return {
      linkCopied: false
    }
  },
  computed: {
    logLevelColorMapper() {
      const vuetifyThemeColors = this.$vuetify.theme.themes.light

      return {
        CRITICAL: vuetifyThemeColors.error,
        DEBUG: vuetifyThemeColors.secondaryGray,
        ERROR: vuetifyThemeColors.error,
        INFO: vuetifyThemeColors.info,
        WARNING: vuetifyThemeColors.warning
      }
    }
  },
  mounted() {
    this.emitRender()
  },
  updated() {
    this.emitRender()
  },
  methods: {
    copyLogLink() {
      setTimeout(() => {
        this.linkCopied = true
        navigator.clipboard.writeText(
          `${window.location.origin}${this.$route.path}?logId=${this.log.id}`
        )

        setTimeout(() => {
          this.linkCopied = false
        }, 3000)
      }, 100) // Should match log-copy transition duration
    },
    // Let parent know if the rendered log's ID is equal to the log ID query param
    emitRender() {
      if (this.isQueriedLog()) {
        this.$emit('query-log-rendered')
      }
    },
    // Determine whether log's ID is equal to the log ID provided via query param
    isQueriedLog() {
      return this.log.id === this.$route.query.logId
    },
    // Determine the log-level color based on the passed-in log level ("DEBUG", "ERROR", etc)
    logLevelColor(logLevel) {
      return (
        this.logLevelColorMapper[logLevel] ||
        this.$vuetify.theme.themes.light.secondaryGray
      )
    }
  }
}
</script>

<template>
  <div
    class="pl-3 pr-5 py-2 log-row"
    :class="{
      'log-row-color-1': !isQueriedLog() && index % 2 === 0,
      'log-row-color-2': !isQueriedLog() && index % 2 !== 0,
      'log-row-color-queried': isQueriedLog()
    }"
    tabindex="0"
  >
    <div class="log-datetime log-subline">
      {{ log.date }} at {{ log.time }} | {{ log.name }}
    </div>
    <div class="log-level log-subline">
      {{ log.level }}
      <v-icon :color="logLevelColor(log.level)" small>lens</v-icon>
    </div>
    <div class="log-message">{{ log.message }}</div>

    <v-tooltip left>
      <template v-slot:activator="{ on }">
        <v-btn
          class="log-link pa-0 ma-0"
          color="primary"
          small
          text
          @click="copyLogLink"
          v-on="on"
        >
          <transition name="log-copy" mode="out-in">
            <v-icon v-if="linkCopied" key="copied">check</v-icon>
            <v-icon v-else key="not-copied">link</v-icon>
          </transition>
        </v-btn>
      </template>
      <span>{{ linkCopied ? 'Copied!' : 'Copy log URL' }}</span>
    </v-tooltip>
  </div>
</template>

<style lang="scss" scoped>
.log-copy-enter-active,
.log-copy-leave-active {
  transition: opacity 100ms;
}

.log-copy-enter,
.log-copy-leave-to {
  opacity: 0;
}

.log-datetime {
  grid-area: datetime;
}

.log-level {
  grid-area: level;
  justify-self: end;
}

.log-link {
  bottom: 0;
  opacity: 0;
  position: absolute;
  right: 6px;

  &:focus,
  &:hover {
    opacity: 1;
  }
}

.log-row {
  display: grid;
  font-family: 'Source Code Pro', monospace;
  grid-template-areas:
    'datetime level'
    'message message';
  grid-template-columns: 2fr 1fr;
  position: relative;

  /* stylelint-disable a11y/selector-pseudo-class-focus */
  &:hover {
    .log-link {
      opacity: 1;
    }
  }

  &:focus {
    z-index: 10;
  }
  /* stylelint-enable a11y/selector-pseudo-class-focus */
}

.log-row-color-1 {
  background-color: #fff;
}

.log-row-color-2 {
  background-color: #f7f7f7;
}

.log-row-color-queried {
  background-color: #e0f4ff;
}

.log-subline {
  font-size: 0.9em;
}

.log-message {
  grid-area: message;
  white-space: pre-wrap; // Needed to format log messages properly
}
</style>
