<template>
  <div class="mb-2">
    <template v-if="showDeleteButton">
      <div class="delete-section__danger-zone">
        <DetailsKeyValue label="Danger Zone" stacked>
          <div
            class="d-flex align-center font-weight-semibold mt-2 content__delete__btn"
          >
            <i class="pi pi-information-line pi-sm mr-1 content-delete__text" />
            <span class="content-delete__text"
              >Deleting this {{label.toLowerCase()}} will delete all its data.</span
            >
          </div>

          <div class="mt-2">
            <m-button
              color="delete"
              miter
              @click="emit('remove', item.id!)"
            >
              Delete {{label}}
            </m-button>
            <m-icon-button
              icon="pi-lg pi-close-line"
              class="delete-section__hide-delete"
                 @click="showDeleteButton = false"
            />
          </div>
        </DetailsKeyValue>
      </div>
    </template>
    <template v-else>
      <DetailsKeyValue :label="deleteLabel" stacked>
        <m-button
          class="delete-section__show-delete"
          @click="showDeleteButton = true"
        >
          Show Delete Button
        </m-button>
      </DetailsKeyValue>
    </template>
  </div>
</template>

<script lang="ts" setup>
import { ref } from "vue"
import { Deployment } from "@/models/Deployment"
import {WorkQueue} from "@/models/WorkQueue"
import DetailsKeyValue from "@/components/DetailsKeyValue.vue"


const props = defineProps<{
  item: Deployment | WorkQueue,
  label: string
}>()

const deleteLabel=`Delete ${props.label}`
const emit = defineEmits<{
  (event: "remove", value: string): void
}>()

const showDeleteButton = ref(false)
</script>

<style lang="scss">
.delete-section__danger-zone {
  position: relative;
  color: var(--error);
  background-color: lighten($error, 30%);
  padding: var(--p-2);
}

.delete-section__hide-delete {
  position: absolute;
  top: 10px;
  right: 10px;
}

.delete-section__show-delete {
  > :first-child {
    border-color: var(--error) !important;
    color: var(--error) !important;
  }
}

.delete-section__show-delete.active {
  > :first-child {
    color: var(--white) !important;
    background-color: var(--error) !important;
  }
}
</style>
