"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  ReactNode,
} from "react";
import { createClient } from "@/lib/supabase";
import { UserInfo, getMe } from "@/lib/api/auth";

interface AuthContextType {
  user: UserInfo | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  isLoading: true,
  login: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const supabaseRef = useRef(createClient());
  // Track if password login is in progress to avoid duplicate getMe() calls
  const loginInProgressRef = useRef(false);

  useEffect(() => {
    const supabase = supabaseRef.current;

    // Load user on mount if session exists
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        getMe().then(setUser).catch(() => setUser(null));
      } else {
        setUser(null);
      }
      setIsLoading(false);
    });

    // Listen for auth state changes (handles magic link + sign out)
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "SIGNED_IN" && session && !loginInProgressRef.current) {
        // Magic link or token refresh — load user from backend
        getMe()
          .then(setUser)
          .catch(() => setUser(null))
          .finally(() => setIsLoading(false));
      } else if (event === "SIGNED_OUT") {
        setUser(null);
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      loginInProgressRef.current = true;
      try {
        const { error } = await supabaseRef.current.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw new Error(error.message);

        // Fetch internal user info from backend
        const me = await getMe();
        setUser(me);
      } finally {
        loginInProgressRef.current = false;
      }
    },
    []
  );

  const logout = useCallback(async () => {
    await supabaseRef.current.auth.signOut();
    setUser(null);
    window.location.href = "/login";
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
