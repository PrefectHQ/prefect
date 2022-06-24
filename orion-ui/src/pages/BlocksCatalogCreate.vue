<template>
  <p-layout-default v-if="blockType" class="blocks-catalog-create">
    <template #header>
      <PageHeadingBlocksCatalogCreate :block-type="blockType" />
    </template>

    <template v-if="blockSchema">
      <BlockSchemaFormCard v-model:data="data" v-model:name="name" :block-schema="blockSchema" v-on="{ submit, cancel }" />
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingBlocksCatalogCreate, useRouteParam, titleCase, BlockSchemaFormCard, BlockDocumentData } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { useSubscriptionWithDependencies } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { useRouter } from 'vue-router'
  import { routes } from '@/router'
  import { blockDocumentsApi } from '@/services/blockDocumentsApi'
  import { blockSchemasApi } from '@/services/blockSchemasApi'
  import { blockTypesApi } from '@/services/blockTypesApi'

  const router = useRouter()
  const data = ref<BlockDocumentData>({})
  const name = ref('')

  const blockTypeNameParam = useRouteParam('blockTypeName')
  const blockTypeSubscriptionArgs = computed<Parameters<typeof blockTypesApi.getBlockTypeByName> | null>(() => {
    if (!blockTypeNameParam.value) {
      return null
    }

    return [titleCase(blockTypeNameParam.value)]
  })

  const blockTypeSubscription = useSubscriptionWithDependencies(blockTypesApi.getBlockTypeByName, blockTypeSubscriptionArgs)
  const blockType = computed(() => blockTypeSubscription.response)

  const blockSchemaSubscriptionArgs = computed<Parameters<typeof blockSchemasApi.getBlockSchemas> | null>(() => {
    if (!blockType.value) {
      return null
    }

    return [
      {
        blockSchemas: {
          blockTypeId: {
            any_: [blockType.value.id],
          },
        },
      },
    ]
  })

  const blockSchemaSubscription = useSubscriptionWithDependencies(blockSchemasApi.getBlockSchemas, blockSchemaSubscriptionArgs)
  const blockSchema = computed(() => blockSchemaSubscription.response?.[0])

  function submit(): void {
    if (!blockSchema.value || !blockType.value) {
      return
    }

    blockDocumentsApi
      .createBlockDocument({
        name: name.value,
        data: data.value,
        blockSchemaId: blockSchema.value.id,
        blockTypeId: blockType.value.id,
      })
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
</script>