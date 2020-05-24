<template>
  <v-container style="max-width: 1440px;" class="pt-0 pb-12">
    <v-row v-if="$slots['row-1-tile']">
      <v-col cols="12" class="pb-0">
        <v-row>
          <v-col class="pb-0">
            <slot name="row-1-tile" />
          </v-col>
        </v-row>
      </v-col>
    </v-row>
    <v-row>
      <v-col cols="12" class="py-0 px-4">
        <v-row>
          <v-col class="pa-0">
            <slot name="row-2-tile" />
          </v-col>
        </v-row>
      </v-col>
    </v-row>
  </v-container>
</template>
