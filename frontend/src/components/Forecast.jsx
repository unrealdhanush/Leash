import React, { createContext, useContext } from "react";
import { Area, AreaChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { money, short } from "../format.js";

export const ReserveContext = createContext(25000);

export default function Forecast({ balances, breach, height = 160 }) {
  const reserve = useContext(ReserveContext);
  const data = balances.map((b, i) => ({ week: i + 1, balance: b }));
  const color = breach ? "#f2994a" : "#5fd3a5";
  return (
    <div className="forecast" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
          <XAxis dataKey="week" tick={{ fill: "#7d8590", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "#2a2f37" }} tickFormatter={(w) => `w${w}`} />
          <YAxis tick={{ fill: "#7d8590", fontSize: 10 }} tickLine={false} axisLine={false} width={38} tickFormatter={short} />
          <Tooltip
            contentStyle={{ background: "#12161c", border: "1px solid #2a2f37", fontFamily: "JetBrains Mono", fontSize: 12 }}
            formatter={(v) => [money(v), "balance"]}
            labelFormatter={(w) => `week ${w}`}
          />
          <ReferenceLine y={reserve} stroke="#e5484d" strokeDasharray="4 3" label={{ value: `reserve ${short(reserve)}`, fill: "#e5484d", fontSize: 10, position: "insideTopRight" }} />
          {breach && <ReferenceLine x={breach} stroke="#f2994a" strokeDasharray="2 2" />}
          <Area type="monotone" dataKey="balance" stroke={color} fill={color} fillOpacity={0.12} strokeWidth={1.6} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
