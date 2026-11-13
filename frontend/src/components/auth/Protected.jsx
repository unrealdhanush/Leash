import React, { createContext, useContext, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { UserButton, useAuth } from "@clerk/react";
import { api, setTokenGetter } from "../../api.js";

const MeContext = createContext(null);
export const useMe = () => useContext(MeContext);

// Hands Clerk's session token to the API client.
export function AuthBridge() {
  const { getToken, isSignedIn } = useAuth();
  setTokenGetter(isSignedIn ? getToken : async () => null);
  return null;
}

export default function Protected({ children, admin }) {
  const { isLoaded, isSignedIn } = useAuth();
  const [me, setMe] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    if (isSignedIn) api.me().then(setMe).catch((e) => setError(e.message));
  }, [isSignedIn]);

  if (!isLoaded) return null;
  if (!isSignedIn) return <Navigate to="/sign-in" replace />;
  if (error) return <Gate title="We could not check your access" text={error} />;
  if (!me) return null;
  if (me.role === "pending") {
    return (
      <Gate
        testid="pending-access"
        title="Waiting for approval"
        text={`You are signed in as ${me.email}. An admin has to let you in before you can start or see purchases.`}
      />
    );
  }
  if (admin && me.role !== "admin") return <Navigate to="/app" replace />;
  return <MeContext.Provider value={me}>{children}</MeContext.Provider>;
}

function Gate({ title, text, testid }) {
  return (
    <div className="gate" data-testid={testid || "access-error"}>
      <Link to="/" className="brand"><span className="mark">L</span><span className="brand-name">Leash</span></Link>
      <h1>{title}</h1>
      <p>{text}</p>
      <UserButton />
    </div>
  );
}

export function AuthPage({ children }) {
  return (
    <div className="authpage" data-testid="auth-page">
      <Link to="/" className="brand"><span className="mark">L</span><span className="brand-name">Leash</span></Link>
      {children}
    </div>
  );
}
