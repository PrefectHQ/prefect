import type { WorkPool } from "@/api/work-pools";
import { cn } from "@/lib/utils";
import { WorkPoolToggle } from "../work-pool-toggle";
import { WorkPoolMenu } from "../work-pool-menu";
import {
  Breadcrumb,
  BreadcrumbList,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbSeparator,
  BreadcrumbPage,
} from "@/components/ui/breadcrumb";

type WorkPoolPageHeaderProps = {
  workPool: WorkPool;
  onUpdate?: () => void;
  className?: string;
};

export const WorkPoolPageHeader = ({
  workPool,
  onUpdate,
  className,
}: WorkPoolPageHeaderProps) => {
  return (
    <header
      className={cn(
        "flex mb-4 flex-row items-center justify-between",
        className,
      )}
    >
      <Breadcrumb className={className}>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink to="/work-pools" className="text-xl font-semibold">
              Work pools
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem className="text-xl font-semibold">
            <BreadcrumbPage>{workPool.name}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <div className="flex items-center space-x-2">
        <WorkPoolToggle workPool={workPool} onUpdate={onUpdate} />
        <WorkPoolMenu workPool={workPool} onUpdate={onUpdate} />
      </div>
    </header>
  );
};
