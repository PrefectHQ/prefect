import { type RefObject, useState, useEffect } from "react";

export const useIsOverflowing = (ref: RefObject<HTMLElement>) => {
	const [isOverflowing, setIsOverflowing] = useState(false);
	useEffect(() => {
		if (ref.current) {
			setIsOverflowing(ref.current.scrollWidth > ref.current.clientWidth);
		}
	}, [ref]);
	return isOverflowing;
};
