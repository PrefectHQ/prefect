<template>
  <m-card shadow="sm">
    <div class="empty-state-card">
      <div class="empty-state-card__background-image" :style="{ backgroundImage }" />
      <div class="empty-state-card__text">
        <h1 class="empty-state-card__letters">
          {{ header }}
        </h1>
        <p class="empty-state-card__letters">
          {{ description }}
        </p>
        <slot>
          <router-link :to="link">
            <m-button color="primary" miter icon="pi-add-line">
              {{ buttonText }}
            </m-button>
          </router-link>
        </slot>
      </div>
      <div class="empty-state-card__example-shadow">
        <div class="empty-state-card__example">
          <slot name="example">
            <img :src="imagePath" :alt="imageAltText" class="empty-state-card__card-image" />
          </slot>
        </div>
      </div>
    </div>
  </m-card>
</template>

<script lang="ts">
  import { defineComponent, PropType } from 'vue'
  import { RouteLocationRaw } from 'vue-router'
  import CircleBackgroundSvg from '@/assets/circlesBackground.svg'

  export default defineComponent({
    name: 'EmptyStateCard',
    expose: [],
    props: {
      buttonText: {
        type: String,
        default: '',
      },

      header: {
        type: String,
        required: true,
      },

      description: {
        type: String,
        required: true,
      },

      link: {
        type: [Object, String] as PropType<RouteLocationRaw>,
        default: '',
      },

      imagePath: {
        type: String,
        default: '',
      },

      imageAltText: {
        type: String,
        default: '',
      },
    },

    data: function() {
      return {
        backgroundImage: `url(${CircleBackgroundSvg})`,
      }
    },
  })
</script>

<style lang="scss">
@use 'sass:map';

.empty-state-card {
  display: flex;
  flex-direction: column;
  text-align: center;
  position: relative;
  overflow: hidden;
  padding: var(--p-2);
  gap: var(--m-3);

  @media only screen and (min-width: map.get($breakpoints, 'lg')) {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    height: 380px;
    padding: 0 80px;
  }

  &__text,
  &__example-shadow {
    position: relative;
    z-index: 2;
  }

  &__text {
    display: flex;
    flex-direction: column;
    justify-content: space-around;
    align-items: center;
    position: relative;

    @media only screen and (min-width: map.get($breakpoints, 'lg')) {
      text-align: left;
      min-width: 250px;
      align-items: flex-start;
    }
  }

  &__example {
    border-radius: 4px;
    overflow: hidden;
    min-width: 500px;
  }

  &__example-shadow {
    filter: $drop-shadow-sm;
  }

  &__letters {
      gap: 8px 0;
      letter-spacing: 0;
    }

  &__card-image {
    position: relative;
    max-height: 235px;
    display: none;

    @media only screen and (min-width: map.get($breakpoints, 'sm')) {
      display: inline-block;
    }
  }

  &__background-image {
    background-size: contain;
    background-repeat: no-repeat;
    height: 1500px;
    width: 1500px;
    top: -150px;
    left: 10vw;
    position: absolute;
    z-index: 1;
    animation: empty-state-card-rotate 40s infinite linear;

    @media only screen and (min-width: map.get($breakpoints, 'md')) {
      left: 50vw;
    }
   }
}

@keyframes empty-state-card-rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>