/** The typed measurements: the fields follow the contract and the entries end up where the engine reads them. */
import { describe, expect, it } from "vitest";
import nominal from "../../../../shared/examples/nominal.json";
import indicators from "../../../../shared/indicators.json";
import { entered, FIELDS, isValid, withEntries } from "./selfReport";

describe("the form's fields", () => {
  it("cover every indicator that has a guide, and nothing else", () => {
    expect(Object.keys(FIELDS).sort()).toEqual(indicators.indicators.map((guide) => guide.signal).sort());
  });

  it("accept what the contract accepts", () => {
    const [glucose] = FIELDS["selfReport.glucoseMgDl"];
    expect([glucose.min, glucose.max]).toEqual([20, 600]);
    expect(isValid(glucose, 95)).toBe(true);
    expect(isValid(glucose, 19)).toBe(false);
    expect(isValid(glucose, Number.NaN)).toBe(false);
    const [mood] = FIELDS["selfReport.mood"];
    expect([mood.min, mood.max, mood.step]).toEqual([1, 5, 1]);
  });
});

describe("withEntries", () => {
  it("leaves the telemetry alone until something is entered", () => {
    expect(withEntries(nominal, {})).toEqual(nominal);
  });

  it("puts each measurement where the contract has it", () => {
    const telemetry = withEntries(nominal, { sleepHoursLast24h: 5, mood: 2, glucoseMgDl: 110, bodyTempC: 36.8, heartRateBpm: 64 });
    expect(telemetry.selfReport).toMatchObject({ sleepHoursLast24h: 5, mood: 2, glucoseMgDl: 110, bodyTempC: 36.8 });
    expect(telemetry.biometrics).toMatchObject({ heartRateBpm: 64, heartRateConfidence: 1 });
    expect(telemetry.biometrics.perclos).toBe(nominal.biometrics.perclos);
  });

  it("needs both numbers of a blood pressure", () => {
    expect(entered("selfReport.bloodPressure", { systolic: 120 })).toBe(false);
    expect(withEntries(nominal, { systolic: 120 }).selfReport.bloodPressure).toEqual(nominal.selfReport.bloodPressure);
    expect(withEntries(nominal, { systolic: 120, diastolic: 80 }).selfReport.bloodPressure).toEqual({ systolic: 120, diastolic: 80 });
  });
});
