import { type RefObject, useEffect, useState } from "react";

export const useIsOverflowing = (ref: RefObject<HTMLElement | null>) => {
	const [isOverflowing, setIsOverflowing] = useState(false);
	useEffect(() => {
		if (ref.current) {
			setIsOverflowing(ref.current.scrollWidth > ref.current.clientWidth);
		}
	}, [ref]);
	return isOverflowing;
};
