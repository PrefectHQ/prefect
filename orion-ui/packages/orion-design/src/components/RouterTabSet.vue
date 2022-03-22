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
  import TabSet from '@/components/TabSet.vue'
  import { RouterTab } from '@/types/tabs'

  const props = defineProps({
    tabs: {
      type: Array as PropType<Readonly<RouterTab[]>>,
      required: true,
      validator:(value: RouterTab[]) => value.length > 0,
    },
  })

  const router = useRouter()

  const getRouteKey = (route: RouterTab['route']): string => {
    return `${route.name}${route.hash ?? ''}`
  }

  const getTabByRouteKey = (routeKey: string | null): RouterTab => {
    const [defaultTab] = props.tabs
    if (!routeKey) {
      return defaultTab
    }

    return props.tabs.find(({ route }) => getRouteKey(route) === routeKey) ?? defaultTab
  }

  const getTabByKey = (key: string | undefined): RouterTab => {
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

  const selectedTab = computed<RouterTab>(() => {
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