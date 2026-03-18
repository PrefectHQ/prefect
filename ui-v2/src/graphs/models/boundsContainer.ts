import { Container } from "pixi.js";

/**
 * This container extends the container from pixi.
 *
 * In pixi.js v7, this overrode the updateTransform and calculateBounds methods
 * to include children whose renderable or visible property was set to false in
 * bounds calculations. This ensured a BoundsContainer would have the same bounds
 * even if some or all of its children were not rendered.
 *
 * In pixi.js v8, the bounds and transform systems were completely rewritten.
 * The v7-specific overrides (updateTransform, calculateBounds, _bounds, _boundsID,
 * worldAlpha, _mask, etc.) no longer exist on Container. The v8 bounds system
 * handles bounds calculation differently, so this class now simply extends Container.
 */
export class BoundsContainer extends Container {}
