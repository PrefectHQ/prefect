<template>
  <list-item>
    <div>
      <i class="item--icon pi pi-deployment pi-2x" />

      <div>
        <div class="item--title subheader">
          {{ deployment.name }}
        </div>
        <Tag
          v-for="tag in deployment.tags"
          :key="tag"
          color="secondary-pressed"
          class="item--tags mr-1"
          outlined
        >
          {{ tag }}
        </Tag>
      </div>
    </div>

    <Button class="ml-auto mr-2" color="outlined">View Parameters</Button>
    <Button color="outlined">Quick Run</Button>
  </list-item>
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import { Deployment } from '@/objects'

class Props {
  deployment = prop<Deployment>({ required: true })
}

@Options({})
export default class ListItemDeployment extends Vue.with(Props) {}
</script>

<style lang="scss">
// @use '@/styles/components/list--item.scss';
</style>
