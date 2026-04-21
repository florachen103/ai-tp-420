"use client";

import { create } from "zustand";
import { api, setToken } from "./api";
import type { User } from "@/types/api";

interface AuthState {
  user: User | null;
  loading: boolean;
  init: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string, verificationCode: string, department?: string) => Promise<void>;
  sendRegisterCode: (email: string) => Promise<void>;
  logout: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  loading: false,
  init: async () => {
    if (typeof window === "undefined") return;
    const token = localStorage.getItem("tp_token");
    if (!token) return;
    try {
      set({ loading: true });
      const user = await api.get<User>("/auth/me");
      set({ user });
    } catch {
      setToken(null);
      set({ user: null });
    } finally {
      set({ loading: false });
    }
  },
  login: async (email, password) => {
    const res = await api.post<{ access_token: string }>("/auth/login", {
      email,
      password,
    });
    setToken(res.access_token);
    const user = await api.get<User>("/auth/me");
    set({ user });
  },
  register: async (email, password, name, verificationCode, department) => {
    await api.post("/auth/register", { email, password, name, department, verification_code: verificationCode });
    const res = await api.post<{ access_token: string }>("/auth/login", {
      email,
      password,
    });
    setToken(res.access_token);
    const user = await api.get<User>("/auth/me");
    set({ user });
  },
  sendRegisterCode: async (email) => {
    await api.post("/auth/send-register-code", { email });
  },
  logout: () => {
    setToken(null);
    set({ user: null });
  },
}));
