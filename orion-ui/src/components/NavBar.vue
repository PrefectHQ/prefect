<template>
  <div class="nav-bar" tabindex="-1">
    <router-link to="/" class="nav-bar__item">
      <img class="nav-bar__logo" src="@/assets/logos/prefect-logo-mark-gradient.svg" />
    </router-link>

    <template v-for="(route, index) in routes" :key="index">
      <router-link
        v-tooltip:right="route.name"
        :to="route.path"
        class="nav-bar__item"
        :class="{ 'nav-bar__item--active': route.name === currentRoute.name }"
      >
        <i :class="`nav-bar__icon pi pi-${route.icon}`" />
      </router-link>
    </template>

    <router-link to="/settings" class="nav-bar__item mt-auto ml-auto">
      <i class="nav-bar__icon pi pi-settings-3-line" />
    </router-link>
  </div>
</template>

<script lang="ts" setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
const currentRoute = useRoute()

const routes = computed(() => {
  return [
    {
      icon: 'flow',
      name: 'Flows',
      path: '/flows',
    },
    {
      icon: 'robot-line',
      name: 'Work Queues',
      path: '/work-queues',
    },
  ]
})
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

@media (max-width: 640px) {
  .nav-bar {
    padding: 0 8px;
    height: 62px;
    flex-direction: row;
    max-width: unset;
    width: 100vw;
  }
}
</style>
