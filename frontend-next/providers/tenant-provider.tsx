"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import { useAuth } from "./auth-provider";

interface TenantContextType {
  selectedCustomerId: number | null;
  customerList: number[];
  selectCustomer: (id: number) => void;
}

const TenantContext = createContext<TenantContextType>({
  selectedCustomerId: null,
  customerList: [],
  selectCustomer: () => {},
});

export function TenantProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | null>(
    null
  );
  const [customerList, setCustomerList] = useState<number[]>([]);

  useEffect(() => {
    if (!user) return;

    const ids = user.customer_ids || [];
    setCustomerList(ids);

    // Restore selection from localStorage or pick first
    const stored = localStorage.getItem("munuiq_customer_id");
    if (stored && ids.includes(Number(stored))) {
      setSelectedCustomerId(Number(stored));
    } else if (ids.length > 0) {
      setSelectedCustomerId(ids[0]);
    }
  }, [user]);

  const selectCustomer = useCallback((id: number) => {
    setSelectedCustomerId(id);
    localStorage.setItem("munuiq_customer_id", String(id));
  }, []);

  return (
    <TenantContext.Provider
      value={{ selectedCustomerId, customerList, selectCustomer }}
    >
      {children}
    </TenantContext.Provider>
  );
}

export function useTenant() {
  return useContext(TenantContext);
}
