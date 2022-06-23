<template>
  <p-layout-default v-if="blockType" class="blocks-catalog-create">
    <template #header>
      <PageHeadingBlocksCatalogCreate :block-type="blockType" />
    </template>
    <p-card class="blocks-catalog-create__card">
      <template v-if="blockSchema">
        <BlockSchemaForm
          v-model:data="data"
          v-model:name="name"
          :block-schema="blockSchema"
          class="blocks-catalog-create__form"
          v-on="{ save, cancel }"
        />
      </template>

      <BlockTypeCard :block-type="blockType" class="block-catalog-create__type" />
    </p-card>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingBlocksCatalogCreate, useRouteParam, titleCase, BlockSchemaForm, BlockDocumentData, BlockTypeCard } from '@prefecthq/orion-design'
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

  function save(): void {
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

<style>
.blocks-catalog-create__card {
  grid-template-areas: "type"
                       "form";
}

@screen md {
  .blocks-catalog-create__card {
    grid-template-areas: "form type";
  }
}

.blocks-catalog-create__card { @apply
  grid
  gap-4
  md:grid-cols-[minmax(0,1fr)_250px]
}

.blocks-catalog-create__form {
  grid-area: form;
}

.block-catalog-create__type {
  align-self: start;
  grid-area: type;
}
</style>