import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Landing from "./pages/Landing.jsx";
import Purchases from "./pages/Purchases.jsx";
import Purchase from "./pages/Purchase.jsx";
import Compare from "./pages/Compare.jsx";
import "./index.css";

createRoot(document.getElementById("root")).render(
  <BrowserRouter>
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/app" element={<Purchases />} />
      <Route path="/app/purchases/:id" element={<Purchase />} />
      <Route path="/app/compare" element={<Compare />} />
    </Routes>
  </BrowserRouter>
);
