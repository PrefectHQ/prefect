import gsap from "gsap";
import { waitForConfig } from "@/graphs/objects/config";
import { cull } from "@/graphs/objects/culling";
import { waitForSettings } from "@/graphs/objects/settings";

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function animationFactory() {
	const settings = await waitForSettings();
	const config = await waitForConfig();

	function animate(
		el: gsap.TweenTarget,
		vars: gsap.TweenVars,
		skipAnimation?: boolean,
	): gsap.core.Tween {
		const skip = settings.disableAnimations || skipAnimation;
		const duration = skip ? 0 : config.animationDuration / 1000;

		return gsap.to(el, {
			...vars,
			duration,
			ease: "power1.out",
			onUpdate: () => {
				cull();
			},
		});
	}

	return {
		animate,
	};
}
