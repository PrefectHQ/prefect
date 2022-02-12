<template>
  <TabSet v-model:value="internalSelectedTabKey" :tabs="tabs">
    <template v-for="(_, name) in $slots" #[name]="slotData">
      <slot :name="name" v-bind="slotData" />
    </template>
  </TabSet>
</template>

<script lang="ts" setup>
  import { computed, PropType } from 'vue'
  import { useRouter } from 'vue-router'
  import TabSet from './TabSet.vue'

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
  }

  const props = defineProps({
    tabs: {
      type: Array as PropType<Tab[]>,
      required: true,
      validator:(value: Tab[]) => value.length > 0,
    },
  })

  const router = useRouter()

  const getRouteKey = (route: Route): string => {
    return `${route.name}${route.hash ?? ''}`
  }

  const getTabByRouteKey = (routeKey: string | null): Tab => {
    const [defaultTab] = props.tabs
    if (!routeKey) {
      return defaultTab
    }

    return props.tabs.find(({ route }) => getRouteKey(route) === routeKey) ?? defaultTab
  }

  const getTabByKey = (key: string | undefined): Tab => {
    const [defaultTab] = props.tabs
    if (!key) {
      return defaultTab
    }

    return props.tabs.find(tab => tab.key === key) ?? defaultTab
  }

  const getHashValue = (hash: string): string => {
    if (hash.startsWith('#')) {
      return hash.substring(1)
    }

    return hash
  }

  const currentRouteRouteKey = computed<string | null>(() => {
    if (typeof router.currentRoute.value.name !== 'string') {
      return null
    }

    const hash = getHashValue(router.currentRoute.value.hash)

    return getRouteKey({ name: router.currentRoute.value.name, hash })
  })

  const selectedTab = computed<Tab>(() => {
    return getTabByRouteKey(currentRouteRouteKey.value)
  })

  const internalSelectedTabKey = computed<string>({
    get: () => selectedTab.value.key,
    set: value => {
      const { name, hash } = getTabByKey(value).route
      const newRoute = { ...router.currentRoute.value, name }

      if (hash) {
        newRoute.hash = `#${hash}`
      }

      router.push(newRoute)
    },
  })
</script>