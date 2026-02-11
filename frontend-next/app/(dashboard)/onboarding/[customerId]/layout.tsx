"use client";

import { useParams, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { WizardStepper } from "@/components/onboarding/wizard-stepper";
import { getOnboardingStatus } from "@/lib/api/onboarding";

const STEPS = [
  { id: "entities", label: "Entities", href: "entities" },
  { id: "categories", label: "Categories", href: "categories" },
  { id: "products", label: "Products", href: "products" },
  { id: "integrations", label: "Integrations", href: "integrations" },
  { id: "validation", label: "Validation", href: "validation" },
];

export default function OnboardingWizardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams();
  const pathname = usePathname();
  const customerId = Number(params.customerId);
  const [completedSteps, setCompletedSteps] = useState<string[]>([]);

  // Determine current step from URL
  const currentStep =
    STEPS.find((s) => pathname.endsWith(s.href))?.id || "entities";

  useEffect(() => {
    getOnboardingStatus(customerId)
      .then((status) => setCompletedSteps(status.completed_steps || []))
      .catch(() => {});
  }, [customerId]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">
          Onboarding — Customer {customerId}
        </h1>
      </div>
      <WizardStepper
        steps={STEPS}
        currentStep={currentStep}
        completedSteps={completedSteps}
      />
      <div>{children}</div>
    </div>
  );
}
