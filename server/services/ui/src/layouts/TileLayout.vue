<template>
  <v-container fluid style="max-width: 1440px;" class="mx-auto pt-0 px-3 pb-12">
    <v-row
      v-if="
        $slots['row-1-col-1-tile-1'] ||
          $slots['row-1-col-2-tile-1'] ||
          $slots['row-1-col-3-tile-1'] ||
          $slots['row-1-col-4-tile-1']
      "
      class="justify-start"
    >
      <v-col
        :class="
          $slots['row-2-col-1-row-1-tile-1'] ||
          $slots['row-2-col-1-row-2-tile-1'] ||
          $slots['row-2-col-1-row-3-tile-1'] ||
          $slots['row-2-col-1-row-4-tile-1']
            ? 'pb-0'
            : ''
        "
      >
        <v-row :style="{ height: $vuetify.breakpoint.mdAndUp ? '351px' : '' }">
          <v-col cols="12" md="4">
            <slot name="row-1-col-1-tile-1" />
          </v-col>
          <v-col cols="12" md="4" sm="6">
            <slot name="row-1-col-2-tile-1" />
          </v-col>
          <v-col cols="12" md="4" sm="6">
            <slot name="row-1-col-3-tile-1" />
          </v-col>

          <!-- This col is just used to push col-4 to the right -->
          <v-col v-if="$vuetify.breakpoint.mdAndUp" cols="4"> </v-col>

          <v-col cols="12" md="8" class="pt-2">
            <slot name="row-1-col-4-tile-1" />
          </v-col>
        </v-row>
      </v-col>
    </v-row>

    <v-row class="justify-start">
      <v-col
        v-if="
          $slots['row-2-col-1-row-1-tile-1'] ||
            $slots['row-2-col-1-row-2-tile-1'] ||
            $slots['row-2-col-1-row-3-tile-1'] ||
            $slots['row-2-col-1-row-4-tile-1']
        "
        cols="12"
        md="4"
        :class="
          $slots['row-1-col-1-tile-1'] ||
          $slots['row-1-col-2-tile-1'] ||
          $slots['row-1-col-3-tile-1'] ||
          $slots['row-1-col-4-tile-1']
            ? 'pt-0'
            : ''
        "
      >
        <v-row v-if="$slots['row-2-col-1-row-1-tile-1']">
          <v-col>
            <slot name="row-2-col-1-row-1-tile-1" />
          </v-col>
        </v-row>

        <v-row v-if="$slots['row-2-col-1-row-2-tile-1']">
          <v-col>
            <slot name="row-2-col-1-row-2-tile-1" />
          </v-col>
        </v-row>

        <v-row v-if="$slots['row-2-col-1-row-3-tile-1']">
          <v-col>
            <slot name="row-2-col-1-row-3-tile-1" />
          </v-col>
        </v-row>

        <v-row v-if="$slots['row-2-col-1-row-4-tile-1']">
          <v-col>
            <slot name="row-2-col-1-row-4-tile-1" />
          </v-col>
        </v-row>
      </v-col>

      <v-col
        v-if="
          $slots['row-2-col-2-row-1-tile-1'] ||
            $slots['row-2-col-2-row-2-tile-1'] ||
            $slots['row-2-col-2-row-2-tile-2'] ||
            $slots['row-2-col-2-row-3-tile-1']
        "
        cols="12"
        md="8"
        :class="
          $slots['row-1-col-1-tile-1'] ||
          $slots['row-1-col-2-tile-1'] ||
          $slots['row-1-col-3-tile-1']
            ? 'pt-0'
            : ''
        "
      >
        <v-row v-if="$slots['row-2-col-2-row-1-tile-1']">
          <v-col>
            <slot name="row-2-col-2-row-1-tile-1" />
          </v-col>
        </v-row>

        <v-row
          v-if="
            $slots['row-2-col-2-row-2-tile-1'] ||
              $slots['row-2-col-2-row-2-tile-2']
          "
        >
          <v-col>
            <slot name="row-2-col-2-row-2-tile-1" />
          </v-col>

          <v-col>
            <slot name="row-2-col-2-row-2-tile-2" />
          </v-col>
        </v-row>

        <v-row v-if="$slots['row-2-col-2-row-3-tile-1']">
          <v-col>
            <slot name="row-2-col-2-row-3-tile-1" />
          </v-col>
        </v-row>
      </v-col>
    </v-row>
  </v-container>
</template>
