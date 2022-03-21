<template>
  <div class="nav-bar" tabindex="-1">
    <router-link to="/" class="nav-bar__item">
      <img class="nav-bar__logo" src="@/assets/logos/prefect-logo-mark-gradient.svg" />
    </router-link>

    <router-link
      to="/flows"
      class="nav-bar__item"
      :class="{ 'nav-bar__item--active': '/flows' === route?.path }"
    >
      <i class="nav-bar__icon pi pi-flow" />
    </router-link>

    <router-link
      to="/work-queues"
      class="nav-bar__item"
      :class="{ 'nav-bar__item--active': '/work-queues' === route?.path }"
    >
      <i class="nav-bar__icon pi pi-robot-line" />
    </router-link>

    <router-link to="/settings" class="nav-bar__item mt-auto ml-auto">
      <i class="nav-bar__icon pi pi-settings-3-line" />
    </router-link>
  </div>
</template>

<script lang="ts" setup>
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<style lang="scss" scoped>
.nav-bar {
  --width: 62px;

  background-color: var(--white);
  box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.06), 0px 1px 3px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 8px 0;
  position: fixed;
  top: 0;
  width: var(--width);
  z-index: var(--layer-nav);
}

.nav-bar__logo {
  width: 24px;
}

.nav-bar__item {
  text-decoration: none;
  height: var(--width);
  width: var(--width);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: width 150ms ease-in-out 150ms;
}

.nav-bar__item:not(:last-child) {
  border-bottom: 1px solid var(--secondary-hover);
}

.nav-bar__item--active {
  background: var(--primary);

  .nav-bar__icon {
    color: var(--white);
  }
}

// .logo {
//   width: 24px;
// }

// .navbar {
//   background-color: #fff;
//   box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.06), 0px 1px 3px rgba(0, 0, 0, 0.1);
//   display: flex;
//   flex-direction: column;
//   height: 100vh;
//   padding: 8px 0;
//   position: fixed;
//   top: 0;
//   width: 62px;
//   z-index: var(--layer-nav);

//   .nav-item {
//     // color: $red !important;
//     text-decoration: none;

//     height: 62px;
//     width: 62px;

//     display: inline-flex;
//     align-items: center;
//     justify-content: center;

//     transition: width 150ms ease-in-out 150ms;
//   }
// }

@media (max-width: 640px) {
  .nav-bar {
    padding: 0 8px;
    height: 62px;
    flex-direction: row;
    max-width: unset;
    width: 100vw;

    .nav-bar__item {
      transition: width 150ms ease-in-out 150ms;
    }
  }
}
</style>
