<template>
  <v-sheet
    tile
    style="max-width: 1440px;"
    class="mx-auto px-6"
    color="appBackground"
  >
    <v-row
      no-gutters
      class="d-flex align-center pb-3"
      :class="$slots.breadcrumbs ? '' : 'py-3'"
    >
      <v-col :sm="$slots['page-actions'] ? 8 : 12">
        <v-row>
          <v-col
            cols="12"
            class="d-flex align-center justify-space-between pb-1"
          >
            <div>
              <div class="overline"><slot name="page-type"></slot></div>
              <div class="headline"><slot name="page-title"></slot></div>
            </div>
          </v-col>
        </v-row>
        <v-row v-if="$slots.breadcrumbs" no-gutters>
          <v-col cols="12" class="pb-1">
            <slot name="breadcrumbs"></slot>
          </v-col>
        </v-row>
      </v-col>
      <v-col
        v-if="$slots['page-actions']"
        cols="12"
        sm="4"
        class="align-self-end text-right"
        :class="$vuetify.breakpoint.smAndDown ? 'text-center' : ''"
      >
        <slot name="page-actions"></slot>
      </v-col>
    </v-row>
    <v-divider />
  </v-sheet>
</template>
