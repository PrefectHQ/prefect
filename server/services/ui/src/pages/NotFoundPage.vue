<template>
  <div
    class="not-found-page fill-height"
    :class="{
      small: $vuetify.breakpoint.sm,
      med: $vuetify.breakpoint.mdAndUp,
      mobile: $vuetify.breakpoint.xs
    }"
  >
    <div class="text">
      <h1>Oh no!</h1>
      <p>
        This page seems to have gone missing.<br />
        Sorry for disrupting your <em>flow</em>.
      </p>

      <v-btn text dark @click="$router.push({ name: 'dashboard' })">
        <v-icon>arrow_back_ios</v-icon>
        Back to dashboard
      </v-btn>
    </div>
  </div>
</template>

<style lang="scss" scoped>
i {
  text-decoration: none;
}

.not-found-page {
  background-color: var(--v-primary-base) !important;
  background-image: url('../assets/backgrounds/not-found.svg') !important;
  background-position: left !important;
  background-repeat: no-repeat !important;
  background-size: cover !important;
  color: #f0faff;
  margin-top: -64px;

  .text {
    position: fixed;
    top: 15%;
  }

  &.small {
    .text {
      left: 25%;
    }
  }

  &.med {
    .text {
      left: 20%;
    }
  }

  &.mobile {
    .text {
      left: 5%;
    }
  }
}
</style>
