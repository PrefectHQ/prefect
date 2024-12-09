import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { Link } from "@tanstack/react-router";

export const BlocksLayout = ({
  children,
}: {
  children?: React.ReactNode;
}) => {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem className="text-xl font-semibold">
              Blocks
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        <Button
          size="icon"
          className="h-7 w-7"
          variant="outline"
          asChild
        >
          <Link to="/blocks/catalog">
            <Icon id="Plus" className="h-4 w-4" />
          </Link>
        </Button>
      </div>
      {children}
    </div>
  );
}; 