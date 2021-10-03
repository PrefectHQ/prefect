<template>
  <div class="navbar" tabindex="-1">
    <router-link to="/" class="nav-item">
      <img class="logo" src="@/assets/logos/prefect-logo-mark-gradient.svg" />
    </router-link>

    <router-link to="/settings" class="nav-item mt-auto ml-auto">
      <i class="pi pi-settings-3-line pi-2x" />
    </router-link>
  </div>
</template>

<script lang="ts">
import { Vue } from 'vue-class-component'

export default class NavBar extends Vue {}
</script>

<style lang="scss" scoped>
.logo {
  width: 24px;
}

.navbar {
  background-color: #fff;
  box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.06), 0px 1px 3px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 8px 0;
  position: fixed;
  top: 0;
  width: 62px;
  z-index: 10;

  .nav-item {
    // color: $red !important;
    text-decoration: none;

    height: 62px;
    width: 62px;

    display: inline-flex;
    align-items: center;
    justify-content: center;

    transition: width 150ms ease-in-out 150ms;
  }
}

@media (max-width: 640px) {
  .navbar {
    padding: 0 8px;
    height: 62px;
    flex-direction: row;
    max-width: unset;
    width: 100vw;

    .nav-item {
      transition: width 150ms ease-in-out 150ms;
    }
  }
}
</style>
