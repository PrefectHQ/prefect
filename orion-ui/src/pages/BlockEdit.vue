<template>
  <p-layout-default v-if="blockDocument" class="block-edit">
    <template #header>
      <PageHeadingBlockEdit :block-document="blockDocument" />
    </template>

    <BlockTypeCardLayout :block-type="blockType">
      <BlockSchemaEditForm v-model:data="data" v-bind="{ name, blockSchema }" v-on="{ submit, cancel }" />
    </BlockTypeCardLayout>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { BlockTypeCardLayout, BlockSchemaEditForm, PageHeadingBlockEdit, BlockDocumentUpdate } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { useRouteParam } from '@prefecthq/vue-compositions'
  import { ref } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router/routes'
  import { blockDocumentsApi } from '@/services/blockDocumentsApi'

  const router = useRouter()
  const blockDocumentId = useRouteParam('blockDocumentId')
  const blockDocument = await blockDocumentsApi.getBlockDocument(blockDocumentId.value)
  const { blockType, blockSchema } = blockDocument
  const data = ref(blockDocument.data)
  const name = ref(blockDocument.name)

  function submit(request: BlockDocumentUpdate): void {
    blockDocumentsApi
      .updateBlockDocument(blockDocument.id, request)
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

  usePageTitle(`Edit Block: ${name.value}`)
</script>