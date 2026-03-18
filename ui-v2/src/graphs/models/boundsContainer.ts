// Not fixing linting errors from pixi source code
/* eslint-disable @typescript-eslint/no-unnecessary-condition */

import { Container, type MaskData } from "pixi.js";

/**
 * This container extends the container from pixi but overrides
 * the updateTransform and calculateBounds methods.
 * The versions of these methods here are functional copies
 * except these version also check children whose renderable
 * or visible property is set to false. This means a BoundsContainer
 * will have the same bounds even if some or all of its children are not
 * rendered. This is important for any container where we need to know the actual
 * size of the container even if its children have been culled.
 */
export class BoundsContainer extends Container {
	public updateTransform(): void {
		if (this.sortableChildren && this.sortDirty) {
			this.sortChildren();
		}

		this._boundsID++;

		this.transform.updateTransform(this.parent.transform);

		// TODO: check render flags, how to process stuff here
		this.worldAlpha = this.alpha * this.parent.worldAlpha;

		for (let i = 0, j = this.children.length; i < j; ++i) {
			const child = this.children[i];

			/**
			 * This if statement has been commented out so children always
			 * have their transform updated for bounds calculation
			 */
			// if (child.visible) {
			child.updateTransform();
			// }
		}
	}

	public calculateBounds(): void {
		this._bounds.clear();

		this._calculateBounds();

		for (const child of this.children) {
			/**
			 * This if statement from the original version has been commented out
			 * we always want all children of this type of container to be included
			 * in the bounds of this container
			 */
			// if (!child.visible || !child.renderable) {
			//   continue
			// }

			child.calculateBounds();

			if (child._mask) {
				const maskObject = (
					(child._mask as MaskData).isMaskData
						? (child._mask as MaskData).maskObject
						: child._mask
				) as Container;

				if (maskObject) {
					maskObject.calculateBounds();
					this._bounds.addBoundsMask(child._bounds, maskObject._bounds);
				} else {
					this._bounds.addBounds(child._bounds);
				}
			} else if (child.filterArea) {
				this._bounds.addBoundsArea(child._bounds, child.filterArea);
			} else {
				this._bounds.addBounds(child._bounds);
			}
		}

		this._bounds.updateID = this._boundsID;
	}
}
