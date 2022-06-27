<template>
  <p-layout-default v-if="blockDocument" class="block-edit">
    <template #header>
      <PageHeadingBlockEdit :block-document="blockDocument" />
    </template>

    <template v-if="blockSchema">
      <BlockSchemaFormCard v-model:data="data" v-model:name="name" :block-schema="blockSchema" v-on="{ submit, cancel }" />
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { BlockSchemaFormCard, BlockDocumentData, PageHeadingBlockEdit } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { useRouteParam } from '@prefecthq/vue-compositions'
  import { ref } from 'vue'
  import { useRouter } from 'vue-router'
  import { routes } from '@/router/routes'
  import { blockDocumentsApi } from '@/services/blockDocumentsApi'

  const router = useRouter()
  const blockDocumentId = useRouteParam('blockDocumentId')
  const blockDocument = await blockDocumentsApi.getBlockDocument(blockDocumentId.value)
  const { blockSchema } = blockDocument
  const data = ref<BlockDocumentData>(blockDocument.data)
  const name = ref(blockDocument.name)

  function submit(): void {
    blockDocumentsApi
      .updateBlockDocument(blockDocument.id, {
        name: name.value,
        data: data.value,
      })
      .then(() => {
        showToast('Block updated successfully', 'success')
        router.push(routes.block(blockDocumentId.value))
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