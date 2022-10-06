<template>
  <p-layout-default v-if="blockType" class="blocks-catalog-create">
    <template #header>
      <PageHeadingBlocksCatalogCreate :block-type="blockType" />
    </template>

    <template v-if="blockType">
      <BlockTypeCardLayout :block-type="blockType">
        <template v-if="blockSchema">
          <BlockSchemaCreateForm :block-schema="blockSchema" v-on="{ submit, cancel }" />
        </template>
      </BlockTypeCardLayout>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingBlocksCatalogCreate, BlockTypeCardLayout, BlockSchemaCreateForm, BlockDocumentCreateNamed } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { useRouteParam, useSubscriptionWithDependencies } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'
  import { blockDocumentsApi } from '@/services/blockDocumentsApi'
  import { blockSchemasApi } from '@/services/blockSchemasApi'
  import { blockTypesApi } from '@/services/blockTypesApi'

  const router = useRouter()

  const blockTypeSlugParam = useRouteParam('blockTypeSlug')
  const blockTypeSubscriptionArgs = computed<Parameters<typeof blockTypesApi.getBlockTypeBySlug> | null>(() => {
    if (!blockTypeSlugParam.value) {
      return null
    }

    return [blockTypeSlugParam.value]
  })

  const blockTypeSubscription = useSubscriptionWithDependencies(blockTypesApi.getBlockTypeBySlug, blockTypeSubscriptionArgs)
  const blockType = computed(() => blockTypeSubscription.response)

  const blockSchemaSubscriptionArgs = computed<Parameters<typeof blockSchemasApi.getBlockSchemaForBlockType> | null>(() => {
    if (!blockType.value) {
      return null
    }

    return [blockType.value.id]
  })

  const blockSchemaSubscription = useSubscriptionWithDependencies(blockSchemasApi.getBlockSchemaForBlockType, blockSchemaSubscriptionArgs)
  const blockSchema = computed(() => blockSchemaSubscription.response)

  function submit(request: BlockDocumentCreateNamed): void {
    blockDocumentsApi
      .createBlockDocument(request)
      .then(({ id }) => {
        showToast('Block created successfully', 'success')
        router.push(routes.block(id))
      })
      .catch(err => {
        showToast('Failed to create block', 'error')
        console.error(err)
      })
  }

  function cancel(): void {
    router.back()
  }

  const title = computed<string>(() => {
    if (blockType.value) {
      return `Create ${blockType.value.name} Block`
    }
    return 'Create Block'
  })
  usePageTitle(title)
</script>