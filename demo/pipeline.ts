/**
 * A data processing pipeline with transforms, filters, and aggregation.
 */

type Record = { [key: string]: string | number | boolean | null };

interface PipelineStep {
  name: string;
  process(records: Record[]): Record[];
}

// --- Transforms ---

class RenameFields implements PipelineStep {
  name = "rename_fields";
  constructor(private mapping: { [oldName: string]: string }) {}

  process(records: Record[]): Record[] {
    return records.map((r) => {
      const out: Record = {};
      for (const [key, value] of Object.entries(r)) {
        const newKey = this.mapping[key] || key;
        out[newKey] = value;
      }
      return out;
    });
  }
}

class CastTypes implements PipelineStep {
  name = "cast_types";
  constructor(private casts: { [field: string]: "number" | "boolean" | "string" }) {}

  process(records: Record[]): Record[] {
    return records.map((r) => {
      const out = { ...r };
      for (const [field, type] of Object.entries(this.casts)) {
        if (field in out && out[field] !== null) {
          switch (type) {
            case "number":
              out[field] = Number(out[field]);
              break;
            case "boolean":
              out[field] = Boolean(out[field]);
              break;
            case "string":
              out[field] = String(out[field]);
              break;
          }
        }
      }
      return out;
    });
  }
}

class ComputeField implements PipelineStep {
  name: string;
  constructor(
    private fieldName: string,
    private compute: (record: Record) => string | number | boolean | null
  ) {
    this.name = `compute_${fieldName}`;
  }

  process(records: Record[]): Record[] {
    return records.map((r) => ({
      ...r,
      [this.fieldName]: this.compute(r),
    }));
  }
}

class FillDefaults implements PipelineStep {
  name = "fill_defaults";
  constructor(private defaults: Record) {}

  process(records: Record[]): Record[] {
    return records.map((r) => {
      const out = { ...r };
      for (const [key, value] of Object.entries(this.defaults)) {
        if (!(key in out) || out[key] === null) {
          out[key] = value;
        }
      }
      return out;
    });
  }
}

// --- Filters ---

class FilterByField implements PipelineStep {
  name: string;
  constructor(
    private field: string,
    private predicate: (value: string | number | boolean | null) => boolean
  ) {
    this.name = `filter_by_${field}`;
  }

  process(records: Record[]): Record[] {
    return records.filter((r) => this.predicate(r[this.field]));
  }
}

class DeduplicateBy implements PipelineStep {
  name: string;
  constructor(private field: string) {
    this.name = `deduplicate_by_${field}`;
  }

  process(records: Record[]): Record[] {
    const seen = new Set<string | number | boolean | null>();
    return records.filter((r) => {
      const val = r[this.field];
      if (seen.has(val)) {
        return false;
      }
      seen.add(val);
      return true;
    });
  }
}

// --- Aggregation ---

interface AggregateResult {
  group: string | number | boolean | null;
  count: number;
  values: Record[];
}

class GroupBy implements PipelineStep {
  name: string;
  private _lastResult: AggregateResult[] = [];

  constructor(private field: string) {
    this.name = `group_by_${field}`;
  }

  process(records: Record[]): Record[] {
    const groups = new Map<string | number | boolean | null, Record[]>();
    for (const r of records) {
      const key = r[this.field];
      if (!groups.has(key)) {
        groups.set(key, []);
      }
      groups.get(key)!.push(r);
    }

    this._lastResult = Array.from(groups.entries()).map(([key, values]) => ({
      group: key,
      count: values.length,
      values,
    }));

    // Flatten back to records with a _group_count field
    const result: Record[] = [];
    for (const [key, values] of groups) {
      for (const v of values) {
        result.push({ ...v, _group_count: values.length });
      }
    }
    return result;
  }

  get aggregated(): AggregateResult[] {
    return this._lastResult;
  }
}

// --- Pipeline runner ---

class Pipeline {
  private steps: PipelineStep[] = [];
  private _log: string[] = [];

  add(step: PipelineStep): Pipeline {
    this.steps.push(step);
    return this;
  }

  run(input: Record[]): Record[] {
    this._log = [];
    let data = [...input];

    for (const step of this.steps) {
      const before = data.length;
      data = step.process(data);
      const msg = `[${step.name}] ${before} → ${data.length} records`;
      this._log.push(msg);
      console.log(msg);
    }

    return data;
  }

  get log(): string[] {
    return [...this._log];
  }
}

// --- Demo ---

const sampleData: Record[] = [
  { name: "Alice", department: "eng", salary: "95000", active: "true", location: "NYC" },
  { name: "Bob", department: "eng", salary: "102000", active: "true", location: "SF" },
  { name: "Charlie", department: "sales", salary: "78000", active: "false", location: "NYC" },
  { name: "Diana", department: "eng", salary: "115000", active: "true", location: "SF" },
  { name: "Eve", department: "sales", salary: "82000", active: "true", location: "NYC" },
  { name: "Frank", department: "hr", salary: "71000", active: "true", location: null },
  { name: "Grace", department: "eng", salary: "98000", active: "true", location: "NYC" },
  { name: "Hank", department: "sales", salary: "78000", active: "true", location: "SF" },
  { name: "Ivy", department: "hr", salary: "68000", active: "false", location: "NYC" },
  { name: "Jack", department: "eng", salary: "110000", active: "true", location: "SF" },
];

const groupByDept = new GroupBy("department");

const pipeline = new Pipeline()
  .add(new CastTypes({ salary: "number", active: "boolean" }))
  .add(new FillDefaults({ location: "UNKNOWN" }))
  .add(new FilterByField("active", (v) => v === true))
  .add(new ComputeField("salary_band", (r) => {
    const s = r.salary as number;
    if (s >= 100000) return "senior";
    if (s >= 80000) return "mid";
    return "junior";
  }))
  .add(groupByDept)
  .add(new RenameFields({ name: "employee_name", department: "dept" }));

console.log("\n=== Running Pipeline ===\n");
const result = pipeline.run(sampleData);

console.log("\n=== Results ===\n");
console.log(`${result.length} records after pipeline:`);
for (const r of result) {
  console.log(`  ${r.employee_name} | ${r.dept} | $${r.salary} | ${r.salary_band} | ${r.location}`);
}

console.log("\n=== Aggregation ===\n");
for (const group of groupByDept.aggregated) {
  console.log(`${group.group}: ${group.count} employees`);
}

console.log("\n=== Pipeline Log ===\n");
for (const entry of pipeline.log) {
  console.log(entry);
}
