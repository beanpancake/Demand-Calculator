import React, { useState } from 'react';
import {
  parseLoad,
  rangeDemandWatts,
  heatDemandWatts,
  additionalFactoredWatts,
  basicLoadWatts,
} from '../utils/demand';

const DemandCalculator: React.FC = () => {
  const [voltage, setVoltage] = useState(240);
  const [area, setArea] = useState('');
  const [range, setRange] = useState('');
  const [heat, setHeat] = useState('');
  const [ac, setAC] = useState('');
  const [additional, setAdditional] = useState('');
  const [result, setResult] = useState<number | null>(null);

  const handleCalculate = () => {
    const v = Number(voltage);
    const areaM2 = parseFloat(area) || 0;
    const rangeW = parseLoad(range, v);
    const heatW = parseLoad(heat, v);
    const acW = parseLoad(ac, v);
    const additionalList = additional
      .split(',')
      .map((s) => parseLoad(s.trim(), v))
      .filter((w) => w > 1500);
    const additionalTotal = additionalList.reduce((sum, w) => sum + w, 0);

    const base = basicLoadWatts(areaM2);
    const heatAc = heatDemandWatts(heatW) + acW;
    const rangeDemand = rangeDemandWatts(rangeW);
    const additionalDemand = additionalFactoredWatts(additionalTotal, rangeW > 0);

    setResult(base + heatAc + rangeDemand + additionalDemand);
  };

  return (
    <div>
      <h1>Residential Demand Calculator</h1>
      <div>
        <label>
          Voltage:
          <input
            type="number"
            value={voltage}
            onChange={(e) => setVoltage(Number(e.target.value))}
          />
        </label>
      </div>
      <div>
        <label>
          Area (m²):
          <input value={area} onChange={(e) => setArea(e.target.value)} />
        </label>
      </div>
      <div>
        <label>
          Range (W or breaker A):
          <input value={range} onChange={(e) => setRange(e.target.value)} />
        </label>
      </div>
      <div>
        <label>
          Heat (W or breaker A):
          <input value={heat} onChange={(e) => setHeat(e.target.value)} />
        </label>
      </div>
      <div>
        <label>
          AC (W or breaker A):
          <input value={ac} onChange={(e) => setAC(e.target.value)} />
        </label>
      </div>
      <div>
        <label>
          Additional Loads &gt;1500 W (comma separated):
          <input
            value={additional}
            onChange={(e) => setAdditional(e.target.value)}
          />
        </label>
      </div>
      <button onClick={handleCalculate}>Calculate</button>
      {result !== null && <p>Total demand: {result.toFixed(0)} W</p>}
    </div>
  );
};

export default DemandCalculator;
