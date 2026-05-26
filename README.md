# MIS Cross-Platform Prototype

This workspace contains the current MIS modernization prototype. The new cross-platform direction is:

- `mis_pwa/`: Python FastAPI + responsive PWA prototype.
- `mis_bridge/`: small C# bridge service for reading real MIS data through `MIS.API.dll`.
- `MIS.Core/`, `二手机未结/`, `MIS.WebAPI1/`: earlier C#/WinForms/WebAPI refactor work kept for compatibility and reference.

The Python PWA is currently the main prototype. It starts with mock data and can switch to the C# bridge when MIS credentials are available.

## Run the PWA

Business documentation:

- [当前业务流动说明书（维修业务重点）](BUSINESS_FLOW.md)

Install dependencies:

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m pip install -r mis_pwa\requirements.txt
```

Start the server:

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m uvicorn backend.app:app --host 0.0.0.0 --port 8088 --app-dir mis_pwa
```

Open:

```text
http://127.0.0.1:8088
```

Default prototype login:

```text
admin / admin
```

## Try the MIS Bridge

Build:

```powershell
powershell -ExecutionPolicy Bypass -File mis_bridge\build.ps1
```

Run with MIS credentials:

```powershell
$env:MIS_USERNAME = "your-mis-username"
$env:MIS_PASSWORD = "your-mis-password"
mis_bridge\bin\MisBridgeServer.exe
```

Enable the bridge provider in `mis_pwa\.env`:

```text
DATA_PROVIDER=bridge
BRIDGE_URL=http://127.0.0.1:8090
```

Then restart the PWA server.

## Git Hygiene

Generated files are ignored:

- Python caches and virtual environments.
- PWA logs and backup output.
- .NET `bin/` and `obj/` folders.
- Compiled `.exe` / `.dll` files.
- Local `.env` secrets.

Keep real MIS credentials out of Git.
