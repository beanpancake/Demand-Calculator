import { useState, type ChangeEvent, type FormEvent } from 'react';

interface FormState {
  voltage: string;
  area: string;
  range: string;
  heat: string;
  ac: string;
  evse: string;
  additional: string[];
  tankless: string;
  sps: string[];
}

interface ApiResponse {
  error?: string;
  result?: Record<string, string>;
}

function App() {
  const [form, setForm] = useState<FormState>({
    voltage: '240',
    area: '',
    range: '',
    heat: '',
    ac: '',
    evse: '',
    additional: [''],
    tankless: '',
    sps: [''],
  });
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const updateField = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm(f => ({ ...f, [key]: value }));
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    updateField(name as keyof FormState, value);
  };

  const handleDynamic = (
    key: 'additional' | 'sps',
    index: number,
    value: string,
  ) => {
    const arr = [...form[key]];
    arr[index] = value;
    if (index === arr.length - 1 && value.trim() !== '') {
      arr.push('');
    }
    updateField(key, arr);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    try {
      const payload = {
        voltage: form.voltage,
        area: form.area,
        range: form.range,
        heat: form.heat,
        ac: form.ac,
        evse: form.evse,
        additional: form.additional.filter(x => x.trim() !== ''),
        tankless: form.tankless,
        sps: form.sps.filter(x => x.trim() !== ''),
      };
      const resp = await fetch('/api/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const text = await resp.text();
      if (!text) {
        setError('Empty response from server');
        return;
      }
      let data: ApiResponse;
      try {
        data = JSON.parse(text) as ApiResponse;
      } catch {
        setError('Invalid JSON response');
        return;
      }
      if (!resp.ok || 'error' in data) {
        setError(data.error || `Server error (${resp.status})`);
      } else {
        setResult(data.result['Final Calculated Load (W)']);
      }
    } catch (err: unknown) {
      setError(String(err));
    }
  };

  return (
    <div style={{ padding: '1rem' }}>
      <h1>Demand Calculator</h1>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <form onSubmit={handleSubmit}>
        <div>
          <label>
            Voltage:
            <input name="voltage" value={form.voltage} onChange={handleChange} />
          </label>
        </div>
        <div>
          <label>
            Area:
            <input name="area" value={form.area} onChange={handleChange} />
          </label>
        </div>
        <div>
          <label>
            Range (A or W):
            <input name="range" value={form.range} onChange={handleChange} />
          </label>
        </div>
        <div>
          <label>
            Heating (A or W):
            <input name="heat" value={form.heat} onChange={handleChange} />
          </label>
        </div>
        <div>
          <label>
            AC (A or W):
            <input name="ac" value={form.ac} onChange={handleChange} />
          </label>
        </div>
        <div>
          <label>
            EVSE (A or W):
            <input name="evse" value={form.evse} onChange={handleChange} />
          </label>
        </div>
        <div>
          <label>Additional Loads &gt;1500W:</label>
          {form.additional.map((val, idx) => (
            <div key={idx}>
              <input
                value={val}
                onChange={e => handleDynamic('additional', idx, e.target.value)}
              />
            </div>
          ))}
        </div>
        <div>
          <label>
            Tankless WH (A or W):
            <input name="tankless" value={form.tankless} onChange={handleChange} />
          </label>
        </div>
        <div>
          <label>Steamers/Pools/Spas:</label>
          {form.sps.map((val, idx) => (
            <div key={idx}>
              <input
                value={val}
                onChange={e => handleDynamic('sps', idx, e.target.value)}
              />
            </div>
          ))}
        </div>
        <button type="submit">Calculate</button>
      </form>
      {result && (
        <div>
          <h2>Result</h2>
          <p>{result} W</p>
        </div>
      )}
    </div>
  );
}

export default App;
