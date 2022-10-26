<template>
  <p-layout-default v-if="blockType" class="blocks-catalog-create">
    <template #header>
      <PageHeadingBlocksCatalogCreate :block-type="blockType" />
    </template>

    <template v-if="blockType">
      <BlockTypeCardLayout :block-type="blockType">
        <template v-if="blockSchema">
          <BlockSchemaCreateForm :key="blockSchema.id" :block-schema="blockSchema" v-on="{ submit, cancel }" />
        </template>
      </BlockTypeCardLayout>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingBlocksCatalogCreate, BlockTypeCardLayout, BlockSchemaCreateForm, BlockDocumentCreateNamed, asSingle } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { useRouteParam, useRouteQueryParam, useSubscriptionWithDependencies } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'
  import { blockDocumentsApi } from '@/services/blockDocumentsApi'
  import { blockSchemasApi } from '@/services/blockSchemasApi'
  import { blockTypesApi } from '@/services/blockTypesApi'

  const router = useRouter()
  const redirect = useRouteQueryParam('redirect')

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
      .then(({ id }) => onSuccess(id))
      .catch(err => {
        showToast('Failed to create block', 'error')
        console.error(err)
      })
  }

  function cancel(): void {
    router.back()
  }

  function onSuccess(id: string): void {
    showToast('Block created successfully', 'success')

    if (redirect.value) {
      const route = router.resolve(asSingle(redirect.value))

      router.push(route)
      return
    }

    router.push(routes.block(id))
  }

  const title = computed<string>(() => {
    if (blockType.value) {
      return `Create ${blockType.value.name} Block`
    }
    return 'Create Block'
  })

  usePageTitle(title)
</script>