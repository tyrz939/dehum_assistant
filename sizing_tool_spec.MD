## Dehumidifier Sizer – Functional Spec (v0.1)

### 1. Purpose

Given a set of room-level inputs, return a **latent moisture load** in **litres per 24 hours**. Down-stream logic will map that number to the nearest dehumidifier model.

---

### 2. Function Signature

```ts
/**
 * Calculate the required moisture-removal capacity for a conditioned space.
 * @param input RoomSizingInput
 * @returns RoomSizingOutput
 */
function calculateDehumLoad(input: RoomSizingInput): RoomSizingOutput
```

---

### 3. Data Contracts

#### 3.1 `RoomSizingInput`

| Field          | Type           | Units          | Required          | Notes                                        |
| -------------- | -------------- | -------------- | ----------------- | -------------------------------------------- |
| `length`       | number         | metres         | ✔                 | Internal wall-to-wall                        |
| `width`        | number         | metres         | ✔                 | ―                                            |
| `height`       | number         | metres         | ✔                 | Average finished ceiling height              |
| `currentRH`    | number         | %              | ✔                 | 0 – 100 (validate)                           |
| `targetRH`     | number         | %              | ✔                 | Must be < `currentRH`                        |
| `indoorTemp`   | number         | °C             | ✔                 | 10 – 40 (validate)                           |
| `ach`          | number         | air changes/hr | ✖ (default = 0.5) | Infiltration + mechanical ventilation        |
| `peopleCount`  | number         | persons        | ✖ (default = 0)   | Latent g/h per person handled in logic later |
| `specialLoads` | SpecialLoad\[] | ―              | ✖                 | Pools, spas, wet laundry, etc.               |
| `outdoorRH`    | number         | %              | ✖                 | Needed if using mass-balance method          |
| `outdoorTemp`  | number         | °C             | ✖                 | ―                                            |
| `usageHours`   | number         | hours/day      | ✖ (default = 24)  | For duty-cycled scenarios                    |

##### `SpecialLoad`

```ts
type SpecialLoad = {
  type: "Pool" | "Spa" | "Laundry" | "Process" | "Custom";
  surfaceArea_m2?: number;   // For Pool/Spa
  evaporationRate_Lph?: number; // If known explicitly
  note?: string;
};
```

---

#### 3.2 `RoomSizingOutput`

| Field              | Type   | Units | Notes                                             |
| ------------------ | ------ | ----- | ------------------------------------------------- |
| `volume`           | number | m³    | Derived = L×W×H                                   |
| `latentLoad_L24h`  | number | L/day | Rounded up to 1 decimal                           |
| `calculationNotes` | string | ―     | Brief summary of assumptions & which formula used |

---

### 4. Validation Rules

1. Reject if any **required** field missing.
2. Hard-range checks:

   * `currentRH`, `targetRH`, `outdoorRH` → 0 – 100.
   * `indoorTemp`, `outdoorTemp` → 0 – 50 °C.
3. `targetRH` **must** be < `currentRH` (else error).
4. Auto-populate defaults for optional fields when not supplied.

---

### 5. Computational Place-holders

*(Actual formulas implemented later; name them clearly so they can be unit-tested.)*

| Step | Placeholder Fn             | Intent                                |
| ---- | -------------------------- | ------------------------------------- |
| 1    | `calcRoomVolume()`         | m³ from L×W×H                         |
| 2    | `calcMoistureDifference()` | g/kg at current vs. target (use temp) |
| 3    | `calcAirMass()`            | ρ\_air × volume                       |
| 4    | `calcInfiltrationLoad()`   | ACH impact                            |
| 5    | `calcOccupantLoad()`       | Perspiration/respiration              |
| 6    | `calcSpecialLoad()`        | Pools, laundry, etc.                  |
| 7    | `aggregateLoads()`         | Sum → L/day                           |

---

### 6. Error Handling

```ts
type SizerError = {
  code: "VALIDATION_ERROR" | "RANGE_ERROR" | "INTERNAL_ERROR";
  message: string;
  field?: string;
};
```

Function should `throw SizerError` on any failure.

---

### 7. Example I/O

**Input**

```json
{
  "length": 6,
  "width": 4,
  "height": 2.4,
  "currentRH": 75,
  "targetRH": 55,
  "indoorTemp": 25,
  "ach": 0.7,
  "peopleCount": 2
}
```

**Output**

```json
{
  "volume": 57.6,
  "latentLoad_L24h": 24.8,
  "calculationNotes": "Used ACH-based method, latent per-person = 0.12 L/hr."
}
```

---

### 8. Non-Goals

* **No** UI/CLI.
* **No** product-selection logic (handled downstream).
* **No** persistence; stateless function.

---

### 9. Future Extensions

* Integrate weather API to auto-fill outdoor conditions by postcode.
* Support imperial units via a `units` flag.
* Multizone mode (array of `RoomSizingInput`).

---
