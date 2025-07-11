import type { JSX } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Icon, type IconId } from "./icons";

const EmptyStateIcon = ({ id }: { id: IconId }): JSX.Element => {
	return <Icon id={id} className="size-12 text-muted-foreground mb-8" />;
};
const EmptyStateTitle = ({
	children,
}: {
	children: React.ReactNode;
}): JSX.Element => <h3 className="text-2xl font-bold">{children}</h3>;

const EmptyStateDescription = ({
	children,
}: {
	children: React.ReactNode;
}): JSX.Element => <p className="text-md text-muted-foreground">{children}</p>;

const EmptyStateActions = ({
	children,
}: {
	children: React.ReactNode;
}): JSX.Element => <div className="flex gap-2 mt-4">{children}</div>;

type EmptyStateProps = {
	children: React.ReactNode;
};
const EmptyState = ({ children }: EmptyStateProps): JSX.Element => (
	<Card>
		<CardContent className="flex flex-col gap-2 items-center justify-center py-16">
			{children}
		</CardContent>
	</Card>
);

export {
	EmptyState,
	EmptyStateIcon,
	EmptyStateTitle,
	EmptyStateDescription,
	EmptyStateActions,
};
