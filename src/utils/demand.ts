export function parseLoad(raw: string, voltage: number): number {
  const s = raw.trim();
  if (!s) return 0;
  const val = parseFloat(s);
  if (!isFinite(val) || val <= 0) return 0;
  if (val <= 500) {
    return val * voltage * 0.8;
  }
  return val;
}

export function rangeDemandWatts(watts: number): number {
  if (watts <= 0) return 0;
  return watts <= 12000 ? 6000 : 6000 + 0.4 * (watts - 12000);
}

export function heatDemandWatts(heatW: number): number {
  return heatW <= 10000 ? heatW : 10000 + 0.75 * (heatW - 10000);
}

export function additionalFactoredWatts(totalAdditionalW: number, hasRange: boolean): number {
  if (totalAdditionalW <= 0) return 0;
  if (hasRange) {
    return 0.25 * totalAdditionalW;
  }
  return totalAdditionalW <= 6000 ? totalAdditionalW : 6000 + 0.25 * (totalAdditionalW - 6000);
}

export function basicLoadWatts(areaM2: number): number {
  return areaM2 <= 90 ? 5000 : 5000 + 1000 * Math.ceil((areaM2 - 90) / 90);
}
