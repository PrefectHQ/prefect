<template>
  <list-item class="list-item--flow d-flex align-start justify-start">
    <i class="item--icon pi pi-map-pin-line text--grey-40 align-self-start" />
    <div
      class="
        item--title
        ml-2
        d-flex
        flex-column
        justify-center
        align-self-start
      "
    >
      <h2>
        {{ deployment.name }}
      </h2>

      <div
        class="
          tag-container
          font-weight-semibold
          nowrap
          caption
          d-flex
          align-bottom
        "
      >
        <span class="mr-1">
          <span class="text--grey-40">Schedule: </span>
          <span class="text--grey-80">{{ schedule }}</span>
        </span>

        <span class="mr-1">
          <span class="text--grey-40">Location: </span>
          <span class="text--grey-80">{{ location }}</span>
        </span>

        <!-- Hiding these for now since they're not in the design but I think we'll need them -->
        <!-- <Tag
          v-for="tag in tags"
          :key="tag"
          color="secondary-pressed"
          class="font--primary caption mr-1"
          icon="pi-label"
          flat
        >
          {{ tag }}
        </Tag> -->
      </div>
    </div>

    <div v-breakpoints="'sm'" class="ml-auto nowrap">
      <Button outlined class="mr-1" @click="parametersDrawerActive = true">
        View Parameters
      </Button>
      <Button outlined>Quick Run</Button>
    </div>
  </list-item>

  <drawer v-model="parametersDrawerActive" show-overlay>
    <template #title>{{ deployment.name }}</template>
    <div v-for="(parameter, i) in parameters" :key="i">
      {{ parameter }}
      <Button @click="secondaryDrawerActive[parameter.name] = true"
        >Click</Button
      >

      <drawer v-model="secondaryDrawerActive[parameter.name]">
        <template #title>{{ parameter.name }}</template>
      </drawer>
    </div>
  </drawer>
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import { Deployment } from '@/objects'

class Props {
  deployment = prop<Deployment>({ required: true })
}

@Options({})
export default class ListItemDeployment extends Vue.with(Props) {
  parametersDrawerActive: boolean = false
  secondaryDrawerActive: { [key: string]: boolean } = {}

  get location(): string {
    return this.deployment.location
  }

  get parameters(): { [key: string]: any }[] {
    return this.deployment.parameters
  }

  get schedule(): any {
    return this.deployment.schedule
  }

  get tags(): string[] {
    return this.deployment.tags
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/components/list-item--deployment.scss';
</style>
