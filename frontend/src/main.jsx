import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { SignIn, SignUp } from "@clerk/react";
import ClerkAuthProvider from "./components/auth/ClerkAuthProvider.jsx";
import Protected, { AuthBridge, AuthPage } from "./components/auth/Protected.jsx";
import Landing from "./pages/Landing.jsx";
import Purchases from "./pages/Purchases.jsx";
import Purchase from "./pages/Purchase.jsx";
import Compare from "./pages/Compare.jsx";
import Shared from "./pages/Shared.jsx";
import Team from "./pages/Team.jsx";
import "./index.css";

createRoot(document.getElementById("root")).render(
  <BrowserRouter>
    <ClerkAuthProvider>
      <AuthBridge />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/sign-in/*" element={<AuthPage><SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" withSignUp fallbackRedirectUrl="/app" /></AuthPage>} />
        <Route path="/sign-up/*" element={<AuthPage><SignUp routing="path" path="/sign-up" signInUrl="/sign-in" fallbackRedirectUrl="/app" /></AuthPage>} />
        <Route path="/app" element={<Protected><Purchases /></Protected>} />
        <Route path="/app/purchases/:id" element={<Protected><Purchase /></Protected>} />
        <Route path="/app/compare" element={<Protected><Compare /></Protected>} />
        <Route path="/app/team" element={<Protected admin><Team /></Protected>} />
        <Route path="/share/:token" element={<Shared />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ClerkAuthProvider>
  </BrowserRouter>
);
