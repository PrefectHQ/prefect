<template>
  <p-layout-default class="artifacts">
    <template #header>
      <PageHeadingArtifacts />
    </template>

    <ArtifactCollections />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import {
    PageHeadingArtifacts,
    ArtifactCollections
  } from '@prefecthq/prefect-ui-library'
  import { usePageTitle } from '@/compositions/usePageTitle'

  usePageTitle('Artifacts')
</script>
