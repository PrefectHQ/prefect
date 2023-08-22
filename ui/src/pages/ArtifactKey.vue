<template>
  <p-layout-default class="artifact">
    <template #header>
      <PageHeadingArtifactKey v-if="artifact" :artifact="artifact" />
    </template>

    <ArtifactDescription v-if="artifact" :artifact="artifact" />

    <template v-if="artifact">
      <ArtifactTimeline v-if="artifact.key" :artifact-key="artifact.key" />
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import {
    PageHeadingArtifactKey,
    ArtifactDescription,
    ArtifactTimeline,
    localization,
    useWorkspaceApi
  } from '@prefecthq/prefect-ui-library'
  import { useSubscription, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const api = useWorkspaceApi()
  const artifactKey = useRouteParam('artifactKey')

  const artifactSubscription = useSubscription(api.artifacts.getArtifactCollection, [artifactKey])
  const artifact = computed(() => artifactSubscription.response)

  const pageTitle = computed<string>(() => {
    if (!artifact.value) {
      return localization.info.artifact
    }

    return `${localization.info.artifact}: ${artifact.value.key}`
  })

  usePageTitle(pageTitle)
</script>
