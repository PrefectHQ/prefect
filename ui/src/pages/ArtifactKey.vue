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
    capitalize,
    useWorkspaceApi
  } from '@prefecthq/prefect-ui-library'
  import { useSubscription, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const api = useWorkspaceApi()
  const artifactId = useRouteParam('artifactId')

  const artifactSubscription = useSubscription(api.artifacts.getArtifact, [artifactId])
  const artifact = computed(() => artifactSubscription.response)

  const pageTitle = computed<string>(() => {
    if (!artifact.value) {
      return localization.info.artifact
    }

    return `${localization.info.artifact}: ${artifact.value.key ?? capitalize(artifact.value.type)}`
  })

  usePageTitle(pageTitle)
</script>
