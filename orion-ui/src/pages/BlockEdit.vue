<template>
  <p-layout-default v-if="blockDocument" class="block-edit">
    <template #header>
      <PageHeadingBlockEdit :block-document="blockDocument" />
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
  import { BlockSchemaForm, BlockTypeCard, BlockDocumentData, PageHeadingBlockEdit, useRouteParam } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { ref } from 'vue'
  import { useRouter } from 'vue-router'
  import { routes } from '@/router/routes'
  import { blockDocumentsApi } from '@/services/blockDocumentsApi'

  const router = useRouter()
  const blockDocumentId = useRouteParam('blockDocumentId')
  const blockDocument = await blockDocumentsApi.getBlockDocument(blockDocumentId.value)
  const { blockSchema, blockType } = blockDocument
  const data = ref<BlockDocumentData>(blockDocument.data)
  const name = ref(blockDocument.name)

  function save(): void {

    blockDocumentsApi
      .updateBlockDocument(blockDocument.id, {
        name: name.value,
        data: data.value,
      })
      .then(({ id }) => {
        showToast('Block updated successfully', 'success')
        router.push(routes.block(id))
      })
      .catch(err => {
        showToast('Failed to update block', 'error')
        console.error(err)
      })
  }

  function cancel(): void {
    router.back()
  }
</script>