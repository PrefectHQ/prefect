import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Link, LinkProps } from "@tanstack/react-router";

interface NavItemProps extends LinkProps {
	icon: React.ReactNode;
	children: React.ReactNode;
	activeOptions?: {
		exact?: boolean;
		from?: string;
	};
}

export function NavItem({
	to,
	icon,
	children,
	activeOptions,
	...props
}: NavItemProps) {
	return (
		<Link
			to={to}
			activeOptions={activeOptions}
			activeProps={{ className: "bg-muted" }}
			{...props}
		>
			{({ isActive }) => (
				<Button
					variant="ghost"
					className={cn(
						"w-full justify-start hover:bg-accent",
						isActive ? "bg-accent" : "",
					)}
				>
					{icon}
					{children}
				</Button>
			)}
		</Link>
	);
}
