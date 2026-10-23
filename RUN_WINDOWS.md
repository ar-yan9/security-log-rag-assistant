# Run Log Lens on Windows

## Before starting

Install Python **3.11** and Node.js **22 LTS** with npm. Open a new PowerShell
window after installation. These commands only install project dependencies in
`.venv` and `frontend/node_modules`; they do not change system Python packages.
No paid key or cloud account is needed. The full setup downloads public models.

## 1. Open the project folder

Extract the project or clone it. In File Explorer, open the folder containing
`setup_project.py`, right-click empty space and choose **Open in Terminal**.
Check:

```powershell
py -3.11 --version
node --version
npm.cmd --version
```

If PowerShell blocks `npm.ps1`, use `npm.cmd`. The setup script does this itself.
You do not need to activate a virtual environment or change execution policy.

## 2. Start with retrieval only

```powershell
py -3.11 setup_project.py
.\.venv\Scripts\python.exe run.py
```

Leave that terminal open. Visit `http://127.0.0.1:8000`. Click **SSH login
failures**, then **Find evidence**. You should see AUTH-002 and source line 2.
This default mode is lexical search. It deliberately does not pretend an LLM ran.

## 3. Enable full semantic + local-model mode

Press **Ctrl+C** in the backend terminal, then:

```powershell
py -3.11 setup_project.py --full
$env:RETRIEVAL_MODE = 'semantic'
$env:LOCAL_GGUF_MODEL = (Resolve-Path '.\models\qwen2.5-0.5b-instruct-q4_k_m.gguf').Path
.\.venv\Scripts\python.exe run.py
```

Refresh the page. Select **Local RAG · checked quotes** and submit the SSH sample.
The first semantic query downloads the public embedding model. Generation runs
on CPU. It may take tens of seconds or more on your laptop. The seven-event demo
is intentionally small; RAM/latency requirements for larger corpora are not yet
benchmarked. Do not buy anything to run this demo.

The model is a small Qwen checkpoint, chosen for a CPU smoke test, not claimed as
the best security model. Larger models need their own comparison and validation.

## 4. Stop or reset

**Ctrl+C** stops the server. These `$env:` settings last only in this terminal.
For retrieval-only mode in the same terminal:

```powershell
Remove-Item Env:LOCAL_GGUF_MODEL -ErrorAction SilentlyContinue
$env:RETRIEVAL_MODE = 'lexical'
.\.venv\Scripts\python.exe run.py
```

No paid service, public server, background monitor or hosted database is started.

## Troubleshooting

- **No Python 3.11 found:** install the 64-bit Python 3.11 distribution, reopen
  PowerShell, then retry. Do not paste Python code at the `>>>` prompt.
- **npm not found:** install Node.js 22 LTS and reopen the terminal.
- **No matching llama-cpp wheel:** the script stops instead of compiling native
  code silently. Check 64-bit Windows/Python 3.11. Share the error, not passwords.
  Retrieval-only mode still works; do not claim the model ran if it did not.
- **Port 8000 already in use:** stop the older Log Lens terminal with Ctrl+C.
- **UI says model not configured:** stop the server, set `LOCAL_GGUF_MODEL` to the
  downloaded file as shown above, and restart. An empty path is not a model.
- **Generation rejected:** quote/citation checks rejected the model output.
  Inspect the retrieved events. Do not edit tests to make invented output pass.
- **Frontend missing:** rerun setup. Or run `npm.cmd ci` and `npm.cmd run build`
  inside `frontend`, then return to the project folder and start `run.py`.
- **Download fails:** no private data is needed for the public models. Do not
  add a token, pay for an API, disable security software or expose the backend.
- **Timeout:** native inference may still be finishing. Wait before submitting
  again. A local model's speed depends on the laptop.

## Developer mode (two terminals)

Backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Frontend, second terminal:

```powershell
cd frontend
npm.cmd run dev
```

Open the localhost URL Vite prints. `/api` is proxied to the loopback backend.
Never bind the backend to `0.0.0.0` or make it public without a separate security
and authentication design.

## Linux equivalent

```sh
python3.11 setup_project.py --full
export RETRIEVAL_MODE=semantic
export LOCAL_GGUF_MODEL="$PWD/models/qwen2.5-0.5b-instruct-q4_k_m.gguf"
.venv/bin/python run.py
```

## What to say about it

"I built a local full-stack log evidence workbench. React calls FastAPI. BGE
creates 384-dimensional vectors and local Qdrant retrieves matching events.
A small Qwen model selects evidence, and code checks exact quotes and citations.
The current demo uses synthetic logs and needs broader evaluation. It does not
confirm incidents or replace structured log analytics."

Before describing a part in an interview, run it yourself and explain why its
limits matter. This guide is setup help, not evidence that the app has run on
your particular Windows laptop.

## Whole-corpus record counts and timeline

Use the second panel, **Count records. Keep the sources.** Leave filters empty
for the whole input. Demo metadata labels two SSH-failure records; one record
summarizes five attempts, so the record count is not an attempt count.
Exact filters only; timestamps need an offset. Export all matched source rows
as JSON. See [structured format](docs/STRUCTURED_LOGS.md) and
[quality/acceptance](docs/QUALITY.md). For larger local models, leave enough free RAM and
close heavy apps as needed; retrieval-only remains useful and does not require Qwen.
