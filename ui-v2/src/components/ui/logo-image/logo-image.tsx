import type React from "react";
import { cn } from "@/utils";

type LogoImageProps = {
	url: string | null;
	alt: string;
	size?: "sm" | "md" | "lg";
	className?: string;
};

const sizeClasses = {
	sm: "h-4 w-4",
	md: "h-8 w-8",
	lg: "h-12 w-12",
};

export const LogoImage: React.FC<LogoImageProps> = ({
	url,
	alt,
	size = "md",
	className,
}) => {
	if (!url) {
		return (
			<div
				className={cn(
					"rounded border bg-muted flex items-center justify-center text-muted-foreground text-xs",
					sizeClasses[size],
					className,
				)}
			>
				{alt.charAt(0).toUpperCase()}
			</div>
		);
	}

	return (
		<img
			src={url}
			alt={alt}
			className={cn(
				"rounded border bg-background/50 backdrop-blur-sm object-contain",
				sizeClasses[size],
				className,
			)}
			onError={(e) => {
				const target = e.target as HTMLImageElement;
				const fallback = document.createElement("div");
				fallback.className = cn(
					"rounded border bg-muted flex items-center justify-center text-muted-foreground text-xs",
					sizeClasses[size],
					className,
				);
				fallback.textContent = alt.charAt(0).toUpperCase();
				target.parentNode?.replaceChild(fallback, target);
			}}
		/>
	);
};
