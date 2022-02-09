<template>
  <div class="router-tabs">
    <m-tabs v-model="internalSelectedRouteKey">
      <m-tab
        v-for="tab in tabs"
        :key="tab.key"
        :href="getRouteKey(tab.route)"
        class="router-tabs__tab"
        :class="classes.tab(tab)"
      >
        <i class="pi" :class="tab.icon" />
        <span class="router-tabs__tab-title">{{ tab.title }}</span>
        <span
          v-if="tab.count"
          class="router-tabs__tab-badge caption"
        >{{ tab.count.toLocaleString() }}</span>
      </m-tab>
    </m-tabs>

    <div class="router-tabs__results">
      <transition-group name="tab-fade" mode="out-in" css>
        <template v-for="tab in tabs" :key="tab.title">
          <slot v-if="isSelected(tab)" :name="tab.key" :tab="tab" />
        </template>
      </transition-group>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed, PropType } from 'vue'
  import { useRouter } from 'vue-router'

  type Route = {
    name: string,
    hash?: string,
  }
  type Tab = {
    title: string,
    key: string,
    route: Route,
    icon?: string,
    class?: string,
    count?: number,
  }

  const props = defineProps({
    tabs: {
      type: Array as PropType<Tab[]>,
      required: true,
      validator:(value: Tab[]) => value.length > 0
    }
  })

  const router = useRouter()

  const classes = computed(() => ({
    tab: (tab: Tab) => [tab.class, {
        'router-tabs__tab--active': isSelected(tab)
      }],
  }))

  const isSelected = (tab: Tab): boolean => {
    return tab.key === selectedTab.value.key
  }

  const getRouteKey = (route: Route): string => {
    return `${route.name}${route.hash ?? ''}`
  }

  const getTabByRouteKey = (routeKey: string | null): Tab => {
    if (!props.tabs.length) {
      throw 'RouterTabs Error: <router-tabs> requires at least one Tab'
    }

    const [defaultTab] = props.tabs
    if (!routeKey) {
      return defaultTab
    }

    return props.tabs.find(({ route }) => getRouteKey(route) === routeKey) ?? defaultTab
  }

  const getHashValue = (hash: string): string => {
    if (hash.startsWith('#')) {
      return hash.substring(1)
    }

    return hash
  }

  const currentRouteRouteKey = computed<string | null>(() => {
    const currentRoute = router.currentRoute.value

    if (typeof currentRoute.name !== 'string') {
      return null
    }

    const hash = getHashValue(currentRoute.hash)

    return getRouteKey({ name: currentRoute.name, hash })
  })

  const selectedTab = computed<Tab>(() => {
    return getTabByRouteKey(currentRouteRouteKey.value)
  })

  const internalSelectedRouteKey = computed<string>({
    get: () => getRouteKey(selectedTab.value.route),
    set: value => {
      const { name, hash } = getTabByRouteKey(value).route
      const newRoute = { ...router.currentRoute.value, name }

      if (hash) {
        newRoute.hash = `#${hash}`
      }

      router.push(newRoute)
    },
  })
</script>

<style lang="scss" scoped>
.router-tabs {
    margin: 40px auto;
}

.router-tabs__tab--active {
    background-color: $primary;
    color: $white;

    .router-tabs__tab-badge {
        background-color: $primary;
        color: $white;
    }
}

.router-tabs__tab-title {
    margin: 0 8px;
}

.router-tabs__tab-badge {
    background-color: $white;
    border-radius: 16px;
    font-weight: 400;
    padding: 0 8px;
    min-width: 24px;
    transition: 150ms all;
}

.tab-fade-enter-active,
.tab-fade-leave-active {
    opacity: 0;
    transition: opacity 150ms ease;
}
</style>