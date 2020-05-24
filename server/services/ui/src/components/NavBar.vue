<script>
import { mapGetters, mapMutations } from 'vuex'
import GlobalSearch from '@/components/GlobalSearch'
import moment from '@/utils/moment'

export default {
  components: { GlobalSearch },
  data() {
    return {
      loading: false,
      pendingInvitations: [],
      menu: false,
      clock: null,
      time: Date.now()
    }
  },
  computed: {
    ...mapGetters('sideDrawer', ['disableOpenButton']),
    notFoundPage() {
      return this.$route.name === 'not-found'
    }
  },
  mounted() {
    clearInterval(this.clock)
    this.clock = setInterval(() => {
      this.time = Date.now()
    }, 1000)
  },
  methods: {
    ...mapMutations('sideNav', ['open']),
    ...mapMutations('refresh', ['add']),
    formatTime(time) {
      let timeObj = moment(time).tz(this.timezone),
        shortenedTz = moment()
          .tz(this.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone)
          .zoneAbbr()
      return `${
        timeObj ? timeObj.format('h:mm A') : moment(time).format('h:mm A')
      } ${shortenedTz}`
    },
    refresh() {
      if (this.$route.name == 'dashboard') {
        this.loading = true
        this.add()
        setTimeout(() => {
          this.loading = false
        }, 1800)
      } else {
        this.$router.push({
          name: 'dashboard'
        })
      }
    }
  }
}
</script>

<template>
  <v-app-bar
    :class="{
      'elevation-0': notFoundPage
    }"
    :color="notFoundPage ? 'transparent' : 'primary'"
    :fixed="!notFoundPage"
    clipped-right
    clipped-left
    :app="!notFoundPage"
  >
    <v-progress-linear
      :active="loading"
      :indeterminate="loading"
      background-color="white"
      color="blue"
      absolute
      bottom
    />
    <v-btn
      color="white"
      text
      data-cy="open-sidenav"
      icon
      large
      class="badge badge--hidden"
      @click="open"
    >
      <v-icon>menu</v-icon>
    </v-btn>

    <router-link :to="{ name: 'dashboard' }">
      <v-btn color="primary" text icon large @click="refresh">
        <img
          class="logo"
          style="pointer-events: none;"
          src="@/assets/logos/logomark-light.svg"
          alt="The Prefect Logo"
        />
      </v-btn>
    </router-link>

    <v-spacer />

    <GlobalSearch class="mr-10" />

    <v-tooltip bottom>
      <template v-slot:activator="{ on }">
        <span class="white--text font-weight-medium" v-on="on">
          {{ formatTime(time) }}
          <v-icon class="material-icons-outlined" color="white" small>
            access_time
          </v-icon>
        </span>
      </template>
      System time
    </v-tooltip>
  </v-app-bar>
</template>

<style lang="scss" scoped>
.logo {
  width: 1rem;
}

.badge {
  overflow: unset;
  position: relative;

  /* stylelint-disable */
  /* Disabling this because the style linter doesn't like the small font-size */
  &::after {
    /* stylelint-enable */
    $badge-size: 12.5px;

    background-color: #da2072;
    border-radius: 50%;
    bottom: 5px;
    content: '';
    font-size: 12px;
    height: $badge-size;
    line-height: $badge-size;
    position: absolute;
    right: 5px;
    text-align: center;
    transition: 0.1s linear all;
    width: $badge-size;
    z-index: 9;
  }

  &.badge--hidden::after {
    content: '' !important;
    transform: scale(0);
  }
}

.cursor-pointer {
  cursor: pointer;
}
</style>
