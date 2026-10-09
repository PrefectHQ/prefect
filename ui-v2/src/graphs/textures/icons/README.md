The icons in this folder are converted into textures and applied to sprites for use in the Pixi application.

These deviate from `prefect-design` icons in three ways:

1. In prefect, icons are assigned `currentColor` as the default fill. Here they need to set to `white` so that they can be colorized by the `tint` property of a sprite.
2. In the `index.ts` file, the import path needs the `?url` suffix so that the SVG is imported in the appropriate format for the Pixi `Texture.from()` function.
3. The root `<svg>` element must declare explicit `width` and `height` attributes of `DEFAULT_TEXT_RESOLUTION` (see `src/graphs/consts.ts`) times its `viewBox` size, e.g. `width="80" height="80" viewBox="0 0 20 20"`. WebGL cannot upload an SVG image without intrinsic dimensions as a texture, so the icon renders as a black box, and the image is rasterized at its intrinsic size, so a smaller size looks blurry when the graph is zoomed in.
