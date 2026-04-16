import { Container } from "pixi.js";

/**
 * In PixiJS v7, this container overrode updateTransform and calculateBounds
 * to include culled children in bounds calculations. In PixiJS v8, the bounds
 * and transform systems have been reworked — Container.getBounds() already
 * measures all children, so the custom overrides are no longer needed.
 * This subclass is kept for type compatibility with existing factory code.
 */
export class BoundsContainer extends Container {}
